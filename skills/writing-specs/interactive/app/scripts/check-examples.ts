import assert from 'node:assert/strict'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import fixture from '../../../../../tests/fixtures/interactive/v2/stage1/logic.json'
import { approveBlockReason, EXAMPLE_OUTCOME_UPDATE_PREFIX, emptyState, exampleOutcomeUpdate, isPayload } from '../src/review-state'
import type { LogicSpec, Scenario } from '../src/spec-types'
import { exampleMarkPlugins, ScenarioExampleView } from '../src/views/scenario-example'

const [result, rejection, invented, gap] = exampleMarkPlugins.map((plugin) => plugin.pattern)

function matches(pattern: RegExp, text: string): string[] {
  assert.ok(pattern.global, `${pattern} must be global`)
  return [...text.matchAll(new RegExp(pattern.source, pattern.flags))].map((m) => m[0])
}

assert.equal(exampleMarkPlugins.length, 4)
assert.deepEqual(matches(result, 'The charge is ✓ queued for May 5; next'), ['✓ queued for May 5'])
assert.deepEqual(matches(rejection, 'An API client ✗ cannot add a second line; ok'), ['✗ cannot add a second line'])
assert.deepEqual(matches(gap, 'Date is [ASK: Does a skip move the date?] here'), ['[ASK: Does a skip move the date?]'])
for (const pattern of [result, rejection, invented, gap]) assert.deepEqual(matches(pattern, '**bold** text'), [])
assert.deepEqual(matches(invented, '"Winback" took 10%\uE000 off'), ['10%\uE000'])
assert.deepEqual(matches(invented, 'Charge 2 on 4\uE000, then'), ['4\uE000'])
assert.deepEqual(matches(invented, '**Subscription**'), [])
assert.deepEqual(matches(invented, 'Coffee line costs $9\uE000.'), ['$9\uE000'])

const rendered = renderToStaticMarkup(React.createElement(ScenarioExampleView, { example: { before: 'Values 10%* and 4*,', steps: ['**Subscription** step'], after: 'done' } }))
assert.equal((rendered.match(/example-invented/g) ?? []).length, 2)
assert.ok(rendered.includes('"example-invented">10%*</span>') && rendered.includes('"example-invented">4*</span>'))
assert.ok(!rendered.includes('<em>'))
assert.ok(/<strong[^>]*>Subscription<\/strong>/.test(rendered))

const base: Scenario = {
  id: 'S1', behavior: 'B1', given: 'g', when: 'w', then: 'Then the spec outcome', alternatives: ['Then alt'], explanation: 'e', provenance: 'claude',
}
const withExample: Scenario = { ...base, example: { before: 'b', steps: ['s'], after: 'a' } }
const state = emptyState(1)
assert.equal(approveBlockReason(state, base, {}), null)
assert.equal(approveBlockReason(state, withExample, {}), null)
const custom = { ...state, scenarioOutcomes: { S1: { choice: 'custom' as const, custom: '  ' } } }
assert.equal(approveBlockReason(custom, withExample, { S1: ['q?'] }), 'outcome-missing')
assert.equal(approveBlockReason(state, base, { S1: ['q?'] }), 'open-ask')
assert.equal(approveBlockReason(state, base, { S1: [] }), null)
assert.equal(approveBlockReason(state, base, { S2: ['q?'] }), null)
const alt = { ...state, scenarioOutcomes: { S1: { choice: 'alt-0' as const, custom: '' } } }
assert.equal(approveBlockReason(alt, withExample, {}), 'outcome-changed')
assert.equal(approveBlockReason(alt, withExample, { S1: ['q?'] }), 'open-ask')
assert.equal(approveBlockReason(alt, base, {}), null)

const update = exampleOutcomeUpdate('Then alt')
assert.ok(update.startsWith(EXAMPLE_OUTCOME_UPDATE_PREFIX))
assert.equal(EXAMPLE_OUTCOME_UPDATE_PREFIX, 'Rewrite this scenario for the outcome I picked: ')
assert.equal(update, 'Rewrite this scenario for the outcome I picked: "Then alt". Update its Then and example together.')

const spec = fixture as unknown as LogicSpec
const payload = { spec, slug: 'x', renderId: 'r', itemHashes: {}, logicMarkdown: '', priorDecisions: null }
assert.equal(isPayload(payload), false)
assert.equal(isPayload({ ...payload, openAsks: {} }), true)
assert.equal(isPayload({ ...payload, openAsks: { S1: ['q?'] } }), true)
assert.equal(isPayload({ ...payload, openAsks: { S1: 'q?' } }), false)
assert.equal(isPayload({ ...payload, openAsks: { S1: [1] } }), false)

console.log('example checks passed.')
