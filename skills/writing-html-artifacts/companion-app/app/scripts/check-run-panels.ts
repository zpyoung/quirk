import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { NeedsYouBanner } from '../src/run/banner'
import { ConfirmDialog, confirmTone, retryLines, stopChainLines } from '../src/run/confirm'
import { TaskDrawer } from '../src/run/drawer'
import { QuestionCard } from '../src/run/question-card'
import type { RunEdge, RunQuestion, RunStatus, RunTask, RunView } from '../src/run/types'

const failures: string[] = []
const check = (name: string, ok: boolean, detail = '') => {
  if (!ok) failures.push(detail ? `${name}: ${detail}` : name)
}
const same = (name: string, got: unknown, want: unknown) =>
  check(name, JSON.stringify(got) === JSON.stringify(want), `got ${JSON.stringify(got)}, want ${JSON.stringify(want)}`)

const mkTask = (id: string, status: RunStatus, extra: Partial<RunTask> = {}): RunTask => ({
  id, title: `Title ${id}`, level: 1, status, attempt: 1, attempts: [], files: 0, ready: true, blocked_by: [],
  downstream: [], labels: [], mismatch: null, ...extra,
})
const mkRun = (tasks: RunTask[], edges: RunEdge[], questions: RunQuestion[]): RunView => ({
  run_id: 'r1', branch: 'b', started_at: 0, counts: {}, last_update_at: 0, stale: null, stale_after_s: 180, now: 0,
  tasks, edges, chains: [], rounds: [], questions,
})
const mkQuestion = (id: string, extra: Partial<RunQuestion> = {}): RunQuestion => ({
  id, prompt: `Prompt ${id}`, options: [{ value: 'a', label: 'Alpha' }, { value: 'b', label: 'Beta' }], asked_at: 0, state: 'open',
  ...extra,
})
const html = (el: Parameters<typeof renderToStaticMarkup>[0]) => renderToStaticMarkup(el)
const boot = { token: 't', session: 's' }
const noop = () => {}

const t6 = mkTask('T6', 'failed', { attempt: 2, reason: 'tests red', downstream: ['T9'] })
const t7 = mkTask('T7', 'failed', { attempt: 2, reason: 'wrote appstate.py (out of scope)', attempts: [
  { n: 1, start: 100, end: 160, outcome: 'retry' }, { n: 2, start: 200, end: 290, outcome: 'failed' },
] })
const run = mkRun(
  [mkTask('T4', 'passed'), mkTask('T5', 'passed'), t6, t7, mkTask('T9', 'queued', { blocked_by: ['T6'] })],
  [
    { from: 'T4', to: 'T5', kind: 'dep' },
    { from: 'T5', to: 'T6', kind: 'order' },
    { from: 'T6', to: 'T9', kind: 'dep' },
  ],
  [],
)

const stop = stopChainLines(run, 'T6')
same('stop title', stop.title, 'Stop the chain from T6?')
same('stop lines', stop.lines, [
  'T6 stays failed; any uncommitted work in its worktree is discarded.',
  "T9 won't run and is marked stopped.",
  'T4 and T5 are committed and stay.',
  'Every other task keeps going.',
])
const stopQueued = stopChainLines(run, 'T9')
same('stop queued first line', stopQueued.lines[0], "T9 won't run and is marked stopped.")
same('stop queued predecessors', stopQueued.lines.slice(1), ['T4 and T5 are committed and stay.', 'Every other task keeps going.'])
const stopRunning = stopChainLines(mkRun([mkTask('T1', 'running')], [], []), 'T1')
same('stop running lines', stopRunning.lines, [
  'T1 stops now; any uncommitted work in its worktree is discarded.',
  'Every other task keeps going.',
])
same(
  'stop single predecessor',
  stopChainLines(mkRun([mkTask('T1', 'passed'), mkTask('T2', 'queued')], [{ from: 'T1', to: 'T2', kind: 'dep' }], []), 'T2').lines[1],
  'T1 is committed and stays.',
)

const retry = retryLines(t7)
same('retry title', retry.title, 'Retry T7?')
same('retry lines', retry.lines, ['This starts attempt 3.', 'The last attempt failed: wrote appstate.py (out of scope).'])
same('retry without reason', retryLines(mkTask('T8', 'failed', { attempt: 1 })).lines, ['This starts attempt 2.'])

const open2 = mkRun([t6], [], [
  mkQuestion('late', { task: 'T6', prompt: 'Later one', asked_at: 20 }),
  mkQuestion('early', { prompt: 'Earlier one', asked_at: 10 }),
])
const banner = html(createElement(NeedsYouBanner, { run: open2, boot, onShow: noop }))
check('banner marker', banner.includes('data-run-part="banner"'))
check('banner region', banner.includes('role="region"') && banner.includes('aria-label="Needs you"'))
check('banner live count', banner.includes('aria-live="polite"'))
check('banner order', banner.indexOf('Earlier one') > -1 && banner.indexOf('Earlier one') < banner.indexOf('Later one'))
check('banner task chip', /<span class="run-chip run-banner-task">T6<\/span>/.test(banner) && banner.includes('Later one') && !banner.includes('T6: '))
check('banner show buttons', banner.split('Show on graph').length - 1 === 2)
check('banner answers in place', (banner.match(/data-run-part="question-answer"/g) ?? []).length === 2 && !banner.includes('data-run-part="question-card"'))
check('banner answer form', (banner.match(/<form/g) ?? []).length === 2 && banner.includes('Send'))
check('banner prompt not repeated visibly', banner.includes('class="run-card-prompt sr-only"'))
const bannerWithCard = html(createElement(NeedsYouBanner, { run: open2, boot, onShow: noop, cardQuestionId: 'late' }))
check('banner hides the form whose card is open', (bannerWithCard.match(/data-run-part="question-answer"/g) ?? []).length === 1 && bannerWithCard.includes('data-question="early"'))

const answeredRun = mkRun([t6], [], [
  mkQuestion('o', { state: 'answered', answer: { question: 'o', source: 'orca', text: 'widen scope', at: 1 } }),
  mkQuestion('s', { state: 'answered', answer: { question: 's', source: 'sdd', label: 'Alpha', pick: 'a', at: 1 } }),
  mkQuestion('t', { state: 'answered', answer: { question: 't', source: 'tab', label: 'Beta', pick: 'b', at: 1 } }),
])
const answeredBanner = html(createElement(NeedsYouBanner, { run: answeredRun, boot, onShow: noop }))
check('banner orca answer', answeredBanner.includes('Answered in orca ask: widen scope'))
check('banner sdd answer', answeredBanner.includes('SDD assumed: Alpha'))
check('banner skips tab answer', !answeredBanner.includes('Beta'))
check('banner dismiss', answeredBanner.split('Dismiss').length - 1 === 2)
check('banner empty', html(createElement(NeedsYouBanner, { run: mkRun([t6], [], []), boot, onShow: noop })) === '')

const store = new Map<string, string>([['quirk-run-dismissed', JSON.stringify([`${answeredRun.run_id}:o`])]])
Object.assign(globalThis, {
  sessionStorage: { getItem: (k: string) => store.get(k) ?? null, setItem: (k: string, v: string) => void store.set(k, v) },
})
const dismissedBanner = html(createElement(NeedsYouBanner, { run: answeredRun, boot, onShow: noop }))
check('banner dismissed hidden', !dismissedBanner.includes('widen scope') && dismissedBanner.includes('SDD assumed: Alpha'))
const otherRun = { ...answeredRun, run_id: `${answeredRun.run_id}-other` }
check('banner dismissal scoped to run', html(createElement(NeedsYouBanner, { run: otherRun, boot, onShow: noop })).includes('widen scope'))
Object.assign(globalThis, { sessionStorage: { getItem: () => { throw new Error('blocked') }, setItem: () => { throw new Error('blocked') } } })
check('banner survives blocked storage', html(createElement(NeedsYouBanner, { run: answeredRun, boot, onShow: noop })).includes('widen scope'))
delete (globalThis as { sessionStorage?: unknown }).sessionStorage

const card = html(createElement(QuestionCard, { question: mkQuestion('q', { recommended: 'b', default: 'a' }), boot, onClose: noop }))
check('card marker', card.includes('data-run-part="question-card"'))
check('card form', card.includes('<form'))
check('card recommended tag', card.includes('Recommended'))
check('card recommended first', card.indexOf('Beta') < card.indexOf('Alpha'))
check('card none preselected', !card.includes('checked'))
check('card other box and send', card.includes('Other') && card.includes('Send'))
const answeredCard = html(createElement(QuestionCard, {
  question: mkQuestion('q', { state: 'answered', answer: { question: 'q', source: 'orca', label: 'Alpha', pick: 'a', at: 1 } }),
  boot,
  onClose: noop,
}))
check('answered card marker', answeredCard.includes('data-run-part="question-card"'))
check('answered card has no form', !answeredCard.includes('<form'))


// banner: the task id is a chip and the prompt stays as written, so "T8 wrote ..." is not prefixed with "T8:"
{
  const dup = mkRun([t6], [], [mkQuestion('d', { task: 'T8', prompt: 'T8 wrote summary.tsx. Widen?' })])
  const out = html(createElement(NeedsYouBanner, { run: dup, boot, onShow: noop }))
  check('banner no duplicated id', !out.includes('T8: T8') && !out.includes('T8:') && out.includes('>T8 wrote summary.tsx. Widen?<'))
  check('banner chip', out.includes('<span class="run-chip run-banner-task">T8</span>'))
  check('banner collapse wrapper', out.includes('run-banner-collapse') && out.includes('data-collapsed="false"'))
}

// question card after your own answer
{
  const mine = html(createElement(QuestionCard, {
    question: mkQuestion('m', { state: 'answered', answer: { question: 'm', source: 'tab', label: 'Beta', pick: 'b', at: 1 } }), boot, onClose: noop,
  }))
  check('own answer note', mine.includes('Sent: Beta. SDD will act on it at its next step.'), mine)
  check('own answer is not refusal wording', !mine.includes('Already answered'))
  check('own answer keeps Close', mine.includes('>Close<'))
  const typedMine = html(createElement(QuestionCard, {
    question: mkQuestion('m2', { state: 'answered', answer: { question: 'm2', source: 'tab', text: 'my words', at: 1 } }), boot, onClose: noop,
  }))
  check('own typed answer note', typedMine.includes('Sent: my words. SDD will act on it at its next step.'))
  const sdd = html(createElement(QuestionCard, {
    question: mkQuestion('m3', { state: 'answered', answer: { question: 'm3', source: 'sdd', label: 'Alpha', pick: 'a', at: 1 } }), boot, onClose: noop,
  }))
  check('sdd answer wording unchanged', sdd.includes('Already answered by SDD: Alpha') && !sdd.includes('Sent:'))
  check('orca answer wording unchanged', answeredCard.includes('Already answered in orca ask: Alpha') && !answeredCard.includes('Sent:'))
}

// radio accessible names separate the label, the recommended tag and the description
{
  const rec = html(createElement(QuestionCard, {
    question: mkQuestion('r', { recommended: 'b', options: [{ value: 'a', label: 'Alpha', description: 'first one' }, { value: 'b', label: 'Beta', description: 'second one' }] }),
    boot, onClose: noop,
  }))
  check('radio recommended hint', /Beta<span class="sr-only">, recommended<\/span>/.test(rec), rec)
  check('radio description separated', /<span class="sr-only">\. <\/span><span class="run-card-option-desc">second one<\/span>/.test(rec))
  check('radio visible tag kept', rec.includes('run-card-tag') && rec.includes('Recommended'))
}

// confirm: Stop chain is danger, Retry stays neutral, Cancel is the default focus target
{
  check('stop tone is danger', confirmTone('stop') === 'danger')
  check('retry tone is neutral', confirmTone('retry') === 'neutral')
  const stopDialog = html(createElement(ConfirmDialog, { title: 'T', lines: ['x'], confirmLabel: 'Stop chain', tone: 'danger', onConfirm: noop, onCancel: noop }))
  const retryDialog = html(createElement(ConfirmDialog, { title: 'T', lines: ['x'], confirmLabel: 'Retry', tone: 'neutral', onConfirm: noop, onCancel: noop }))
  check('stop confirm has the danger class', /<button[^>]*class="[^"]*run-confirm-danger[^"]*"[^>]*>(?:<[^>]*>)*Stop chain/.test(stopDialog), stopDialog)
  check('retry confirm has no danger class', !retryDialog.includes('run-confirm-danger'))
  check('cancel never carries the danger class', !/run-confirm-danger[^>]*>(?:<[^>]*>)*Cancel/.test(stopDialog))
  check('cancel is marked as the initial focus', stopDialog.includes('run-confirm-cancel'))
}

// drawer links are clearly links that open a new tab
{
  const links = html(createElement(TaskDrawer, { run, task: { ...t7, round: 'CP1' }, boot, serverNow: 0, onClose: noop }))
  check('drawer link hint', (links.match(/\(opens in a new tab\)/g) ?? []).length === 2)
  check('drawer link class', (links.match(/class="run-link-button"/g) ?? []).length === 2)
  check('drawer scrim', links.includes('run-drawer-scrim'))
}

const drawer = html(createElement(TaskDrawer, { run, task: t7, boot, serverNow: 0, onClose: noop }))
check('drawer marker', drawer.includes('data-run-part="drawer"'))
check('drawer stop chain', drawer.includes('Stop chain'))
check('drawer retry', drawer.includes('>Retry<'))
check('drawer diff link', drawer.replace(/&amp;/g, '&').includes('href="/?view=diff&task=T7"'))
check('drawer new tab', drawer.includes('target="_blank"') && drawer.includes('rel="noreferrer"'))
check('drawer attempts', drawer.includes('1m 00s') && drawer.includes('1m 30s'))
check('drawer no findings link without round', !drawer.includes('view=findings'))
const roundDrawer = html(createElement(TaskDrawer, { run, task: { ...t7, round: 'CP1' }, boot, serverNow: 0, onClose: noop }))
check('drawer findings link', roundDrawer.replace(/&amp;/g, '&').includes('href="/?view=findings&round=CP1"'))
const pendingStop = html(createElement(TaskDrawer, { run, task: { ...t7, pending_action: 'stop' }, boot, serverNow: 0, onClose: noop }))
check('drawer pending stop text', pendingStop.includes('Stop requested, waiting for SDD'))
check('drawer pending hides actions', !pendingStop.includes('Stop chain') && !pendingStop.includes('>Retry<'))
const pendingRetry = html(createElement(TaskDrawer, { run, task: { ...t7, pending_action: 'retry' }, boot, serverNow: 0, onClose: noop }))
check('drawer pending retry text', pendingRetry.includes('Retry requested, waiting for SDD'))
const passedDrawer = html(createElement(TaskDrawer, { run, task: mkTask('T4', 'passed'), boot, serverNow: 0, onClose: noop }))
check('drawer passed has no actions', !passedDrawer.includes('Stop chain') && !passedDrawer.includes('>Retry<'))
const withTree = html(createElement(TaskDrawer, { run, task: { ...t7, worktree: '/wt/T7' }, boot, serverNow: 0, onClose: noop }))
check('drawer open in orca with a worktree', withTree.includes('Open in Orca'))
check('drawer no open in orca without a worktree', !drawer.includes('Open in Orca'))
const endedRun = { ...run, ended: { at: 1, outcome: 'clean' as const } }
const endedTree = html(createElement(TaskDrawer, { run: endedRun, task: { ...t7, worktree: '/wt/T7' }, boot, serverNow: 0, onClose: noop }))
check('drawer no open in orca after the run ended', !endedTree.includes('Open in Orca'))
const evil = html(createElement(TaskDrawer, {
  run, task: mkTask('T1', 'running', { contract_md: '<script>alert(1)</script>\n\n**bold**', title: '<img src=x>' }), boot, serverNow: 0, onClose: noop,
}))
check('drawer escapes contract html', !evil.includes('<script>') && evil.includes('&lt;script&gt;'))
check('drawer renders markdown', evil.includes('<strong>bold</strong>'))
check('drawer escapes title', !evil.includes('<img'))

// a task waiting on you can be answered from its drawer
{
  const asking = { ...run, questions: [mkQuestion('dq', { task: 'T7', prompt: 'Drawer prompt' }), mkQuestion('other', { task: 'T6', prompt: 'Not this task' })] }
  const out = html(createElement(TaskDrawer, { run: asking, task: t7, boot, serverNow: 0, onClose: noop }))
  check('drawer answer form', out.includes('data-run-part="question-answer"') && out.includes('data-question="dq"') && out.includes('<form'))
  check('drawer answer prompt visible', out.includes('Drawer prompt') && !out.includes('run-card-prompt sr-only'))
  check('drawer only its own question', !out.includes('Not this task'))
  check('drawer without a question has no form', !drawer.includes('question-answer'))
}

if (failures.length) {
  console.error(`run-panels-check failed:\n- ${failures.join('\n- ')}`)
  process.exitCode = 1
} else {
  console.log('run-panels-check passed: banner, question card, drawer and confirm text.')
}
