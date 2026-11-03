import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { NeedsYouBanner } from '../src/run/banner'
import { TaskDrawer } from '../src/run/drawer'
import { QuestionCard } from '../src/run/question-card'
import { Reviews } from '../src/run/reviews'
import { RunSummary } from '../src/run/summary'
import { Timeline } from '../src/run/timeline'
import type { RunQuestion, RunTask, RunView } from '../src/run/types'

const question: RunQuestion = {
  id: 'q1', prompt: 'Which?', options: [{ value: 'a', label: 'A' }, { value: 'b', label: 'B' }], asked_at: 0, state: 'open',
}
const task: RunTask = {
  id: 'T1', title: 'Task', level: 1, status: 'running', attempt: 1, attempts: [], files: 0, ready: true, blocked_by: [],
  downstream: [], labels: [], mismatch: null,
}
const run: RunView = {
  run_id: 'r1', branch: 'b', started_at: 0, counts: {}, last_update_at: 0, stale: null, stale_after_s: 180, now: 0,
  tasks: [task], edges: [], chains: [], rounds: [], questions: [question],
}
const boot = { token: 't', session: 's' }
const noop = () => {}

const rendered: [string, string][] = [
  ['banner', renderToStaticMarkup(createElement(NeedsYouBanner, { run, onShow: noop }))],
  ['question-card', renderToStaticMarkup(createElement(QuestionCard, { question, boot, onClose: noop }))],
  ['drawer', renderToStaticMarkup(createElement(TaskDrawer, { run, task, boot, serverNow: 0, onClose: noop }))],
  ['timeline', renderToStaticMarkup(createElement(Timeline, { run, serverNow: 0 }))],
  ['reviews', renderToStaticMarkup(createElement(Reviews, { run }))],
  ['summary', renderToStaticMarkup(createElement(RunSummary, { run, companionStopped: false }))],
]
const missing = rendered.filter(([name, html]) => !html.includes(`data-stub="${name}"`)).map(([name]) => name)
if (missing.length) {
  console.error(`run-panels-check failed: did not render: ${missing.join(', ')}`)
  process.exitCode = 1
} else {
  console.log('run-panels-check passed: the panels render.')
}
