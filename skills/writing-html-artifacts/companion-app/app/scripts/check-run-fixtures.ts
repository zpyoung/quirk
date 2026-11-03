import { readdirSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { RunPage } from '../src/run/run-view'
import type { RunView } from '../src/run/types'
import type { Boot, Snapshot } from '../src/types'

/** Renders every view the fold produces (`fixtures/run/views`) through the run page and pins each scenario's key text. */
const VIEWS = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../fixtures/run/views')

const failures: string[] = []
const check = (ok: boolean, message: string) => {
  if (!ok) failures.push(message)
}

const boot: Boot = { token: 't', session: 's' }
const snapshot = (run: RunView): Snapshot => ({
  rev: 1, mode: 'app', step: null, step_state: 'open', status: null, stages: [], decisions: [], chat: [], threads: [],
  review_registered: false, run,
})
const render = (run: RunView) => renderToStaticMarkup(createElement(RunPage, { snapshot: snapshot(run), boot, paused: false }))
const escaped = (text: string) => text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/'/g, '&#x27;').replace(/"/g, '&quot;')
const has = (html: string, text: string) => html.includes(text) || html.includes(escaped(text))

const names = readdirSync(VIEWS).filter((file) => file.endsWith('.json')).map((file) => file.slice(0, -5)).sort()
check(names.length > 0, `no view fixtures in ${VIEWS}`)

const scenarios: Record<string, (html: string, run: RunView) => void> = {
  'wave-start': (html, run) => {
    const counts = run.counts
    const line = `${counts.passed} of ${run.tasks.length} passed · ${counts.running} running · ${counts.queued} queued`
    check(has(html, line), `wave-start: header lacks the counts line ${JSON.stringify(line)}`)
  },
  'failed-blocked': (html, run) => {
    check(has(html, 'blocked by T7'), 'failed-blocked: lacks "blocked by T7"')
    const failed = run.tasks.find((task) => task.status === 'failed')
    check(!!failed?.reason && has(html, failed.reason), 'failed-blocked: lacks the failed task reason')
  },
  mismatch: (html, run) => {
    const texts = run.tasks.flatMap((task) => (task.mismatch ? [task.mismatch.text] : []))
    check(texts.length > 0, 'mismatch: the fixture has no mismatch')
    for (const text of texts) check(has(html, text), `mismatch: lacks ${JSON.stringify(text)}`)
  },
  'needs-you': (html) => {
    const items = [...html.matchAll(/<li class="run-banner-item" data-kind="open">(.*?)<\/li>/g)].map((m) => m[1])
    check(items.length === 2, `needs-you: ${items.length} banner items, expected 2`)
    check(
      items.length === 2 && items[0].includes('T5') && items[1].includes('T9'),
      'needs-you: banner items are not oldest first (T5 then T9)',
    )
  },
  'answered-orca': (html) => {
    check(has(html, 'Answered in orca ask'), 'answered-orca: lacks "Answered in orca ask"')
  },
  ended: (html) => {
    check(has(html, '<h2>Run finished</h2>'), 'ended: lacks the summary heading')
  },
  stale: (html) => {
    check(html.includes('data-stale="true"'), 'stale: lacks data-stale="true"')
    check(has(html, 'No update for 4 min'), 'stale: lacks "No update for 4 min"')
  },
}

for (const name of names) {
  const run = JSON.parse(readFileSync(path.join(VIEWS, `${name}.json`), 'utf8')) as RunView
  const html = render(run)
  scenarios[name]?.(html, run)
  check(!html.includes('data-stub'), `${name}: renders a data-stub placeholder`)
  // the agent's own status line may say "Wave"; the page's own text must not
  const chrome = render({ ...run, status_text: undefined })
  check(!/Level|Wave/.test(chrome), `${name}: the page mentions a level or a wave`)
}
for (const name of Object.keys(scenarios)) check(names.includes(name), `${name}: scenario has no view fixture`)

if (failures.length) {
  console.error(`run-fixtures-check failed:\n${failures.map((f) => `  - ${f}`).join('\n')}`)
  process.exitCode = 1
} else {
  console.log(`run-fixtures-check passed: ${names.length} fold views render with their scenario text.`)
}
