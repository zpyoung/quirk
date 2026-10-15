import assert from 'node:assert/strict'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import fixture from '../../../../../tests/fixtures/interactive/v2/stage1/logic.json'
import { approveBlockReason, EXAMPLE_OUTCOME_UPDATE_PREFIX, emptyState, exampleOutcomeUpdate, isPayload } from '../src/review-state'
import type { LogicSpec, Scenario } from '../src/spec-types'
import { EXAMPLE_PHRASE, exampleMarkPlugins, ScenarioExampleView } from '../src/views/scenario-example'
import { SpecMarkdown } from '../src/views/shared'

const [invented, gap] = exampleMarkPlugins.map((plugin) => plugin.pattern)

function matches(pattern: RegExp, text: string): string[] {
  assert.ok(pattern.global, `${pattern} must be global`)
  return [...text.matchAll(new RegExp(pattern.source, pattern.flags))].map((m) => m[0])
}

assert.equal(exampleMarkPlugins.length, 2)
assert.deepEqual(matches(EXAMPLE_PHRASE, 'The charge is ✓ queued for May 5; next'), ['✓ queued for May 5'])
assert.deepEqual(matches(EXAMPLE_PHRASE, 'An API client ✗ cannot add a second line; ok'), ['✗ cannot add a second line'])
assert.deepEqual(matches(gap, 'Date is [ASK: Does a skip move the date?] here'), ['[ASK: Does a skip move the date?]'])
for (const pattern of [EXAMPLE_PHRASE, invented, gap]) assert.deepEqual(matches(pattern, '**bold** text'), [])
assert.deepEqual(matches(invented, '"Winback" took 10%\uE000 off'), ['10%\uE000'])
assert.deepEqual(matches(invented, 'Charge 2 on 4\uE000, then'), ['4\uE000'])
assert.deepEqual(matches(invented, '**Subscription**'), [])
assert.deepEqual(matches(invented, 'Coffee line costs $9\uE000.'), ['$9\uE000'])
assert.deepEqual(matches(invented, '$100.00\uE000'), ['$100.00\uE000'])

const rendered = renderToStaticMarkup(React.createElement(ScenarioExampleView, { example: { before: 'Values 10%* and 4*,', steps: ['**Subscription** step'], after: 'done' } }))
assert.equal((rendered.match(/example-invented/g) ?? []).length, 2)
assert.ok(rendered.includes('"example-invented">10%*</span>') && rendered.includes('"example-invented">4*</span>'))
assert.ok(!rendered.includes('<em>'))
assert.ok(/<strong[^>]*>Subscription<\/strong>/.test(rendered))

const MARKDOWN_WRAPPER = '<span class="astryx-markdown[^"]*"[^>]*>'

const starred = renderToStaticMarkup(React.createElement(ScenarioExampleView, { example: { before: 'b', steps: ['s'], after: '✓ total 4*' } }))
assert.equal((starred.match(/class="example-result"/g) ?? []).length, 1)
assert.ok(new RegExp(`<span class="example-result">${MARKDOWN_WRAPPER}[^<]*<span class="example-invented">4\\*</span></span></span>`).test(starred))
assert.equal((starred.match(/example-invented/g) ?? []).length, 1)

const nestedResult = renderToStaticMarkup(React.createElement(ScenarioExampleView, { example: { before: 'b', steps: ['s'], after: '✓ **Subscription** saved' } }))
assert.equal((nestedResult.match(/class="example-result"/g) ?? []).length, 1)
assert.ok(new RegExp(`<span class="example-result">${MARKDOWN_WRAPPER}✓ <strong[^>]*>Subscription</strong> saved</span></span>`).test(nestedResult))

const nestedRejection = renderToStaticMarkup(React.createElement(ScenarioExampleView, { example: { before: 'b', steps: ['s'], after: '✗ The change is ignored; **Charge 2** stays' } }))
assert.equal((nestedRejection.match(/class="example-rejection"/g) ?? []).length, 1)
assert.ok(new RegExp(`<span class="example-rejection">${MARKDOWN_WRAPPER}✗ The change is ignored</span></span>${MARKDOWN_WRAPPER}; <strong[^>]*>Charge 2</strong> stays</span>`).test(nestedRejection))

const lines = renderToStaticMarkup(React.createElement(ScenarioExampleView, { example: { before: 'Charge 1 ✓ queued\nCharge 2 ✗ skipped', steps: ['s'], after: 'a' } }))
assert.equal((lines.match(/class="example-result"/g) ?? []).length, 1)
assert.equal((lines.match(/class="example-rejection"/g) ?? []).length, 1)
assert.ok(lines.includes('<br/>'))

assert.deepEqual(matches(invented, '4,5 and $1,000,$2,000'), ['4', '5', '$1,000', '$2,000'])
const adjacent = renderToStaticMarkup(React.createElement(ScenarioExampleView, { example: { before: 'Values 4*,5* and $1,000*,$2,000*', steps: ['s'], after: '✓ totals 4*,5*' } }))
assert.deepEqual(adjacent.match(/(?<="example-invented">)[^<]*/g), ['4*', '5*', '$1,000*', '$2,000*', '4*', '5*'])

for (const before of ['one\rtwo', 'one\r\ntwo', 'Charge 1 ✓ queued\rCharge 2 ✗ skipped']) {
  const html = renderToStaticMarkup(React.createElement(ScenarioExampleView, { example: { before, steps: ['s'], after: 'a' } }))
  assert.ok(/<br\s*\/?>/.test(html), `a line break in ${JSON.stringify(before)} must render as a hard break`)
  assert.ok(!html.includes('\r'))
}
const crPhrases = renderToStaticMarkup(React.createElement(ScenarioExampleView, { example: { before: 'Charge 1 ✓ queued\rCharge 2 ✗ skipped', steps: ['s'], after: 'a' } }))
assert.equal((crPhrases.match(/class="example-result"/g) ?? []).length, 1)
assert.equal((crPhrases.match(/class="example-rejection"/g) ?? []).length, 1)

const invent = renderToStaticMarkup(React.createElement(ScenarioExampleView, { example: { before: 'x 10%* y', steps: ['s'], after: 'a' } }))
assert.ok(invent.includes('"example-invented">10%*</span>'))

const literal = renderToStaticMarkup(React.createElement(ScenarioExampleView, { example: { before: 'Literal value\uE000', steps: ['s \uE000 and 3*'], after: '✓ kept\uE000' } }))
assert.ok(literal.includes('Literal value\uE000') && literal.includes('s \uE000 and '))
assert.ok(literal.includes('kept\uE000</span>'))
assert.equal((literal.match(/example-invented/g) ?? []).length, 1)
assert.ok(literal.includes('"example-invented">3*</span>'))
assert.ok(!literal.includes('\uE001'))

const HOSTILE_LINK = '[click](jAvAsCrIp:alert(1))'
const GOOD_LINK = '[ok](https://x.y)'
const specLink = renderToStaticMarkup(React.createElement(SpecMarkdown, null, `${HOSTILE_LINK} ${GOOD_LINK}`))
const exampleLink = renderToStaticMarkup(React.createElement(ScenarioExampleView, { example: { before: HOSTILE_LINK, steps: [GOOD_LINK], after: `✓ ${HOSTILE_LINK}` } }))
for (const html of [specLink, exampleLink]) {
  assert.ok(!/href="jAvAsCrIp/i.test(html), 'a javascript: href must never reach the page')
  assert.ok(html.includes('click'))
  assert.ok(/<a [^>]*href="https:\/\/x\.y"[^>]*>ok<\/a>/.test(html))
}
assert.equal((specLink.match(/<a /g) ?? []).length, 1)
assert.equal((exampleLink.match(/<a /g) ?? []).length, 1)
for (const href of ['#frag', 'mailto:a@b.c', ' HTTP://x.y']) {
  const html = renderToStaticMarkup(React.createElement(SpecMarkdown, null, `[t](${href})`))
  assert.ok(html.includes('<a '), `${href} must stay a link`)
}
for (const href of ['vbscript:x', 'data:text/html,x', '/relative', 'ftp://x.y']) {
  const html = renderToStaticMarkup(React.createElement(SpecMarkdown, null, `[t](${href})`))
  assert.ok(!html.includes('<a '), `${href} must render as plain text`)
}

const long = 'a'.repeat(80_000)
const startedAt = performance.now()
renderToStaticMarkup(React.createElement(ScenarioExampleView, { example: { before: long, steps: [long], after: `✓ ${long}` } }))
assert.ok(performance.now() - startedAt < 500, 'a long run without a star must render in linear time')

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
