import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { RunGraph } from '../src/run/graph'
import type { RunView } from '../src/run/types'

const run: RunView = {
  run_id: 'r1', branch: 'b', started_at: 0, counts: {}, last_update_at: 0, stale: null, stale_after_s: 180, now: 0,
  tasks: [], edges: [], chains: [], rounds: [], questions: [],
}
const html = renderToStaticMarkup(
  createElement(RunGraph, { run, serverNow: 0, selected: null, focus: null, cardTask: null, card: null, stale: false, onSelect: () => {} }),
)
if (!html.includes('data-stub="graph"')) {
  console.error('run-graph-check failed: the graph did not render')
  process.exitCode = 1
} else {
  console.log('run-graph-check passed: the graph renders.')
}
