import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { DiffPage, DiffView } from '../src/run/diff-page'
import { FindingsPage } from '../src/run/findings-page'
import { Reviews } from '../src/run/reviews'
import { RunSummary } from '../src/run/summary'
import { Timeline } from '../src/run/timeline'
import type { RunDiff, RunRound, RunTask, RunView } from '../src/run/types'

const failures: string[] = []
function expect(name: string, html: string, includes: string[], excludes: string[] = []): void {
  for (const text of includes) if (!html.includes(text)) failures.push(`${name}: missing ${JSON.stringify(text)}`)
  for (const text of excludes) if (html.includes(text)) failures.push(`${name}: should not contain ${JSON.stringify(text)}`)
}

function task(id: string, patch: Partial<RunTask> = {}): RunTask {
  return {
    id, title: `Title of ${id}`, level: 1, status: 'queued', attempt: 1, attempts: [], files: 0, ready: true,
    blocked_by: [], downstream: [], labels: [], mismatch: null, ...patch,
  }
}

const round: RunRound = {
  id: 'CP1', kind: 'checkpoint', title: 'Checkpoint 1', covers: ['T1', 'T2'], outcome: 'fixes',
  findings: [
    { id: 'CP1-X1', lens: 'correctness', severity: 'high', ruling: 'accepted', reason: 'off by one', fix_task: 'T3' },
    { id: 'CP1-S1', lens: 'scope', severity: 'low', ruling: 'dismissed', reason: 'covered by T4' },
  ],
}

function makeRun(patch: Partial<RunView> = {}): RunView {
  return {
    run_id: 'r1', branch: 'sdd/r1', started_at: 1000, counts: {}, last_update_at: 1100, stale: null, stale_after_s: 180, now: 1200,
    tasks: [
      task('T1', {
        status: 'passed', started_at: 1000, ended_at: 1100,
        attempts: [{ n: 1, start: 1000, end: 1050, outcome: 'failed' }, { n: 2, start: 1060, end: 1100, outcome: 'passed' }],
      }),
      task('T2', { status: 'running', started_at: 1030, attempts: [{ n: 1, start: 1030 }] }),
      task('T3'),
    ],
    edges: [], chains: [], rounds: [round], questions: [], ...patch,
  }
}

const run = makeRun()

// Timeline
const waterfallRun = makeRun({
  tasks: [
    task('T1', {
      status: 'passed',
      attempts: [{ n: 1, start: 1000, end: 1050, outcome: 'failed' }, { n: 2, start: 1060, end: 1100, outcome: 'passed' }],
    }),
    task('T2', { status: 'running', attempts: [{ n: 1, start: 1030 }] }),
    task('T3', { blocked_by: ['T2'] }),
  ],
  edges: [{ from: 'T1', to: 'T2', kind: 'dep' }, { from: 'T2', to: 'T3', kind: 'dep' }],
})
const timeline = renderToStaticMarkup(createElement(Timeline, { run: waterfallRun, serverNow: 1200_000 }))
expect('timeline', timeline, ['data-run-part="timeline"', 'data-attempt="1"', 'data-attempt="2"', 'T1', 'Title of T1', 'T2', '0m 50s', '2m 50s', 'run-timeline-now'], [
  'Level', 'Wave',
])
if (timeline.indexOf('T1') > timeline.indexOf('T2')) failures.push('timeline: rows must follow first attempt start')
expect('timeline true size', timeline, ['viewBox="0 0 880 ', 'width="880"'])
expect('timeline queued row', timeline, ['data-task="T3" data-queued="true"', 'blocked by T2', 'run-timeline-queued'])
if (timeline.indexOf('data-task="T3"') < timeline.indexOf('data-task="T2"')) failures.push('timeline: queued rows must sit below started rows')
expect('timeline dep connector', timeline, ['run-timeline-link run-timeline-link--dep" data-from="T1" data-to="T2"'], ['data-from="T2" data-to="T3"'])
expect('timeline axis ticks', timeline, ['data-tick="0"', 'data-tick="30"', '>0<', '>+30s<'])
{
  const ordered = makeRun({
    tasks: [
      task('T1', { status: 'passed', attempts: [{ n: 1, start: 1000, end: 1050, outcome: 'passed' }] }),
      task('T2', { status: 'passed', attempts: [{ n: 1, start: 1060, end: 1100, outcome: 'passed' }] }),
    ],
    edges: [{ from: 'T1', to: 'T2', kind: 'order' }],
    ended: { at: 1100, outcome: 'clean' },
  })
  const html = renderToStaticMarkup(createElement(Timeline, { run: ordered, serverNow: 1200_000 }))
  expect('timeline order connector', html, ['run-timeline-link--order" data-from="T1" data-to="T2"'], ['run-timeline-now'])
}
const idle = renderToStaticMarkup(createElement(Timeline, { run: makeRun({ tasks: [task('T9')] }), serverNow: 1200_000 }))
expect('timeline empty', idle, ['No task has started yet.', 'data-run-part="timeline"'], ['<svg'])

// Timeline: in-progress segments are coloured by task status and a legend names the statuses shown
{
  const live = makeRun({
    tasks: [
      task('T1', { status: 'retrying', attempts: [{ n: 1, start: 1000, end: 1050, outcome: 'retry' }, { n: 2, start: 1060 }] }),
      task('T2', { status: 'needs-you', attempts: [{ n: 1, start: 1030 }] }),
      task('T3', { status: 'running', attempts: [{ n: 1, start: 1040 }] }),
      task('T4', { status: 'failed', attempts: [{ n: 1, start: 1040, end: 1100, outcome: 'failed' }] }),
    ],
  })
  const html = renderToStaticMarkup(createElement(Timeline, { run: live, serverNow: 1200_000 }))
  const segFor = (taskId: string, n: number) => html.match(new RegExp(`data-task="${taskId}".*?class="run-timeline-seg ([^"]*)" data-attempt="${n}"`))?.[1]
  expect('timeline retrying seg', segFor('T1', 2) ?? '', ['run-timeline-seg--retrying'])
  expect('timeline needs-you seg', segFor('T2', 1) ?? '', ['run-timeline-seg--needs-you'])
  expect('timeline running seg', segFor('T3', 1) ?? '', ['run-timeline-seg--running'])
  expect('timeline failed seg', segFor('T4', 1) ?? '', ['run-timeline-seg--failed'])
  expect('timeline legend', html, ['run-timeline-legend', 'data-status="retrying"', 'data-status="needs-you"', 'data-status="running"', 'data-status="failed"'], ['data-status="queued"'])
  if (html.indexOf('run-timeline-legend') > html.indexOf('run-timeline-axis')) failures.push('timeline: the legend must sit above the axis')
}

// Reviews
const reviews = renderToStaticMarkup(createElement(Reviews, { run }))
expect('reviews', reviews, [
  'data-run-part="reviews"', 'Checkpoint 1', '2 findings · 1 accepted', '✓ CP1-X1', 'fix T3 · CP1', '✗ CP1-S1 dismissed: covered by T4',
  '/?view=findings&amp;round=CP1', 'target="_blank"', 'Findings',
])

// Summary
const ended = makeRun({ ended: { at: 1150, outcome: 'clean', next_step: 'pr' } })
const summary = renderToStaticMarkup(createElement(RunSummary, { run: ended, companionStopped: false }))
expect('summary', summary, ['data-run-part="summary"', 'Run finished', 'sdd/r1', 'Next: open a PR', 'T1', 'T2', 'T3', '1m 40s', 'Checkpoint 1', 'fixes'], [
  'The companion has stopped',
])
const stopped = renderToStaticMarkup(createElement(RunSummary, { run: ended, companionStopped: true }))
expect('summary stopped', stopped, ['The companion has stopped; this is the final state.'])
const blocked = renderToStaticMarkup(
  createElement(RunSummary, { run: makeRun({ ended: { at: 1150, outcome: 'blocked' } }), companionStopped: false }),
)
expect('summary blocked', blocked, ['Run blocked'], ['Next:'])
const halted = renderToStaticMarkup(
  createElement(RunSummary, { run: makeRun({ ended: { at: 1150, outcome: 'stopped', next_step: 'keep' } }), companionStopped: false }),
)
expect('summary stopped outcome', halted, ['Run stopped', 'Next: keep the branch'])
const merged = renderToStaticMarkup(
  createElement(RunSummary, { run: makeRun({ ended: { at: 1150, outcome: 'clean', next_step: 'merge' } }), companionStopped: false }),
)
expect('summary merge', merged, ['Next: merge'])

// Diff
const diff: RunDiff = {
  task: 'T1', base: 'abcdef1234567', head: '1234567abcdef', source: 'commit', truncated: true,
  files: [
    { path: 'a.py', status: 'modified', binary: false, patch: '@@ -1 +1 @@\n-old\n+new <script>alert(1)</script>\n context\n' },
    { path: 'logo.png', status: 'added', binary: true, patch: '' },
  ],
}
const diffHtml = renderToStaticMarkup(createElement(DiffView, { diff, task: 'T1' }))
expect('diff', diffHtml, [
  'data-line="add"', 'data-line="del"', 'Binary file', 'Diff truncated at 1 MiB.', 'abcdef1', '1234567', 'committed', 'a.py',
  'modified', 'logo.png', '&lt;script&gt;',
], ['<script>', 'abcdef12'])
const working = renderToStaticMarkup(createElement(DiffView, { diff: { ...diff, head: null, source: 'worktree', truncated: false }, task: 'T1' }))
expect('diff worktree', working, ['in progress'], ['Diff truncated'])
expect('diff missing', renderToStaticMarkup(createElement(DiffView, { diff: null, task: 'T7' })), ['No diff for T7.'])
expect('diff page', renderToStaticMarkup(createElement(DiffPage, { task: 'T1' })), ['T1', 'Refresh', 'data-run-part="diff-page"'])

// Findings page
expect('findings unknown', renderToStaticMarkup(createElement(FindingsPage, { run, round: 'nope' })), ['No review round nope.', 'data-run-part="findings-page"'])
expect('findings connecting', renderToStaticMarkup(createElement(FindingsPage, { run: null, round: 'CP1' })), ['Connecting to the companion', 'data-run-part="findings-page"'])
expect('findings round', renderToStaticMarkup(createElement(FindingsPage, { run, round: 'CP1' })), [
  'data-run-part="findings-page"', 'Checkpoint 1', '✓ CP1-X1', 'correctness', 'high', 'scope', 'low',
])

if (failures.length) {
  console.error(`run-pages-check failed:\n${failures.join('\n')}`)
  process.exitCode = 1
} else {
  console.log('run-pages-check passed: timeline, reviews, summary, diff and findings pages render.')
}
