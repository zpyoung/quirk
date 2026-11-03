import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { DiffPage } from '../src/run/diff-page'
import { FindingsPage } from '../src/run/findings-page'

const rendered: [string, string][] = [
  ['diff-page', renderToStaticMarkup(createElement(DiffPage, { task: 'T1' }))],
  ['findings-page', renderToStaticMarkup(createElement(FindingsPage, { run: null, round: 'cp1' }))],
]
const missing = rendered.filter(([name, html]) => !html.includes(`data-stub="${name}"`)).map(([name]) => name)
if (missing.length) {
  console.error(`run-pages-check failed: did not render: ${missing.join(', ')}`)
  process.exitCode = 1
} else {
  console.log('run-pages-check passed: the diff and findings pages render.')
}
