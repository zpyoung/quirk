import assert from 'node:assert/strict'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import fixture from '../../../../../tests/fixtures/interactive/v2/stage1/logic.json'
import { approveBlockReason, EXAMPLE_OUTCOME_UPDATE_PREFIX, emptyState, exampleOutcomeUpdate, isPayload } from '../src/review-state'
import type { LogicSpec, Scenario, ScenarioExample } from '../src/spec-types'
import { EXAMPLE_PHRASE, EXAMPLE_PHRASE_PLUGIN, exampleMarkPlugins, ScenarioExampleView } from '../src/views/scenario-example'
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

const render = (example: ScenarioExample) => renderToStaticMarkup(React.createElement(ScenarioExampleView, { example }))
const countOf = (html: string, pattern: RegExp) => (html.match(pattern) ?? []).length

assert.equal(EXAMPLE_PHRASE_PLUGIN.pattern.source, '[✓✗][^;\\n]+')
assert.ok(EXAMPLE_PHRASE_PLUGIN.pattern.global)
assert.deepEqual(matches(EXAMPLE_PHRASE_PLUGIN.pattern, 'a ✓ queued; b ✗ skipped\nc'), ['✓ queued', '✗ skipped'])

const detailsOnly = render({ details: { title: 'Pricing rules', body: 'Plain **bold** body' } })
assert.ok(detailsOnly.includes('aria-label="Pricing rules"'))
assert.ok(/class="example-pane example-details"/.test(detailsOnly))
assert.ok(/<span[^>]*>Pricing rules<\/span>/.test(detailsOnly), 'the title must show as the visible label')
assert.ok(/<strong[^>]*>bold<\/strong>/.test(detailsOnly))
for (const gone of ['Data before', 'Walkthrough', 'Data after', 'example-grid', 'example-before', 'example-after']) assert.ok(!detailsOnly.includes(gone), `${gone} must not render for a details-only example`)

const both = render({ before: 'b', steps: ['s'], after: 'a', details: { title: 'Edge cases', body: 'body' } })
const order = ['Data before', 'Walkthrough', 'Data after', 'aria-label="Edge cases"'].map((part) => both.indexOf(part))
assert.ok(order.every((at) => at >= 0) && order.every((at, i) => i === 0 || at > order[i - 1]), 'the grid must render before the details pane')
assert.equal(countOf(both, /example-details/g), 1)

const dataOnly = render({ before: 'b', steps: ['s'], after: 'a' })
assert.ok(!dataOnly.includes('example-details'))

const table = render({ details: { title: 'Rates', body: '| Plan | Rate |\n| --- | --- |\n| Basic | 10%* |\n| Pro | ✓ saved |' } })
assert.ok(/<table[\s>]/.test(table) && /<\/table>/.test(table), 'a Markdown table in the body must render as a table')
assert.equal(countOf(table, /<tr[\s>]/g), 3)
assert.ok(table.includes('"example-invented">10%*</span>'))
assert.equal(countOf(table, /class="example-result"/g), 1)

const bodyMarks = render({ details: { title: 'Marks', body: 'Total 4* and ✓ charge queued for 3*; then ✗ nothing changes\n\nDate [ASK: Does a skip move the date?] here\n\n- ✓ in a list\n- plain_name stays plain' } })
assert.equal(countOf(bodyMarks, /class="example-result"/g), 2)
assert.equal(countOf(bodyMarks, /class="example-rejection"/g), 1)
assert.equal(countOf(bodyMarks, /class="example-gap"/g), 1)
assert.ok(bodyMarks.includes('"example-invented">4*</span>'))
assert.ok(new RegExp(`class="example-result">✓ charge queued for <span class="example-invented">3\\*</span></span>`).test(bodyMarks), 'a value inside a phrase nests inside the phrase colour')
assert.ok(bodyMarks.includes('Does a skip move the date?'))
assert.ok(!bodyMarks.includes('') && !bodyMarks.includes(''))

const FORBIDDEN = /[​]/
const codeSpan = render({ details: { title: 'Code', body: 'Use `✓ queued; 4* [ASK: why?] a_b` here' } })
const codeSpanText = codeSpan.match(/<code[^>]*>([\s\S]*?)<\/code>/)
assert.ok(codeSpanText, 'an inline code span must render as code')
assert.equal(codeSpanText[1], '✓ queued; 4* [ASK: why?] a_b')
assert.ok(!/example-(result|rejection|invented|gap)/.test(codeSpan), 'marks inside a code span must stay plain')
assert.ok(!FORBIDDEN.test(codeSpan))

const fenced = render({ details: { title: 'Fence', body: 'Before 2* here\n\n```json\n{"a_b": "✓ ok; ✗ no", "n": 4*, "g": "[ASK: why?]"}\n```\n\n~~~\n✗ tilde 3* a_b\n~~~\n\nAfter 5*' } })
const codeBlocks = [...fenced.matchAll(/<code[^>]*>([\s\S]*?)<\/code>/g)].map((m) => m[1].replace(/<[^>]+>/g, ''))
assert.equal(codeBlocks.length, 2)
assert.ok(codeBlocks[0].includes('{&quot;a_b&quot;: &quot;✓ ok; ✗ no&quot;, &quot;n&quot;: 4*, &quot;g&quot;: &quot;[ASK: why?]&quot;}'))
assert.ok(codeBlocks[1].includes('✗ tilde 3* a_b'))
assert.equal(countOf(fenced, /class="example-invented"/g), 2, 'only the two values outside the fence are marked')
assert.ok(!/example-(result|rejection|gap)/.test(fenced))
assert.ok(!FORBIDDEN.test(fenced))

const literalInCode = render({ details: { title: 'Literal', body: 'Out  and a_b and 6*\n\n```\nin  code\n```\n\n`span `' } })
assert.ok(literalInCode.includes('in  code') && literalInCode.includes('span '))
assert.ok(literalInCode.includes('Out  and a_'))
assert.ok(!literalInCode.includes(''))
assert.equal(countOf(literalInCode, /example-invented/g), 1)

const crlfBody = render({ details: { title: 'Newlines', body: 'one 1*\r\n\r\ntwo ✓ ok\r\n\r\n```\r\nkeep_this 2*\r\n```' } })
assert.ok(!crlfBody.includes('\r'))
assert.equal(countOf(crlfBody, /role="paragraph"/g), 2)
assert.equal(countOf(crlfBody, /class="example-result"/g), 1)
assert.ok(crlfBody.includes('keep_this 2*</span>'))
assert.ok(render({ details: { title: 'CR', body: 'one 1*\r\rtwo ✓ ok' } }).includes('example-result'))

const detailsLink = render({ details: { title: 'Links', body: `${HOSTILE_LINK} ${GOOD_LINK}\n\n| a |\n| - |\n| ${HOSTILE_LINK} |` } })
assert.ok(!/href="jAvAsCrIp/i.test(detailsLink) && !/javascript:/i.test(detailsLink.replace(/>[^<]*</g, '><')))
assert.equal(countOf(detailsLink, /<a /g), 1)
assert.ok(detailsLink.includes('click'))

const longBody = 'a'.repeat(80_000)
const bodyStartedAt = performance.now()
render({ details: { title: 'Long', body: `${longBody} \`${longBody}\`\n\n${'`a '.repeat(20_000)}\n\n${'x*'.repeat(20_000)} ✓ ${longBody}` } })
assert.ok(performance.now() - bodyStartedAt < 1500, 'a long details body must render in linear time')

const ZWSP = '\u200b'
const PLACEHOLDER = /[\uE000\uE001]/
const codeText = (html: string) => [...html.matchAll(/<code[^>]*>([\s\S]*?)<\/code>/g)].map((m) => m[1].replace(/<[^>]+>/g, ''))
const MARKED_LINE = 'a_b 4* ✓ ok'
for (const [name, body] of [
  ['bullet', `- \`\`\`\n  ${MARKED_LINE}\n  \`\`\``],
  ['ordered', `1. \`\`\`\n   ${MARKED_LINE}\n   \`\`\``],
  ['paren ordered', `1) \`\`\`\n   ${MARKED_LINE}\n   \`\`\``],
  ['nested list in a quote', `> - \`\`\`\n>   ${MARKED_LINE}\n>   \`\`\``],
  ['nested lists', `- outer\n  1. \`\`\`\n     ${MARKED_LINE}\n     \`\`\`\n\nAfter 5*`],
  ['tilde in a list', `* ~~~\n  ${MARKED_LINE}\n  ~~~`],
] as const) {
  const html = render({ details: { title: 'Listed fence', body } })
  const blocks = codeText(html)
  assert.equal(blocks.length, 1, `${name}: the fence must render as one code block`)
  assert.ok(blocks[0].includes(MARKED_LINE), `${name}: code contents must render as written`)
  assert.ok(!html.includes(ZWSP) && !PLACEHOLDER.test(html), `${name}: no guard characters may reach the page`)
  assert.ok(!/example-(result|rejection|invented|gap)/.test(html.replace(/<span class="example-invented">5\*<\/span>/g, '')), `${name}: no mark spans inside the code`)
}
const afterListFence = render({ details: { title: 'Listed fence', body: `- \`\`\`\n  keep_me 1*\n  \`\`\`\n\nout_side 2*` } })
assert.ok(afterListFence.includes('out_' + ZWSP + 'side'), 'prose after the closed list fence is guarded again')
assert.equal(countOf(afterListFence, /example-invented/g), 1)

const escapedTicks = render({ details: { title: 'Escaped', body: 'Escaped \\` 4* \\` and 5*' } })
assert.equal(countOf(escapedTicks, /class="example-invented"/g), 2, 'a backslash-escaped backtick opens no code span')
assert.ok(escapedTicks.includes('"example-invented">4*</span>') && escapedTicks.includes('"example-invented">5*</span>'))
const escapedThenReal = render({ details: { title: 'Escaped', body: 'Lead \\`a_b `x_y 3*` and \\\\`c_d 6*` end 7*' } })
assert.deepEqual(codeText(escapedThenReal), ['x_y 3*', 'c_d 6*'])
assert.equal(countOf(escapedThenReal, /class="example-invented"/g), 1, 'only the value outside both spans is marked')
const backslashInSpan = render({ details: { title: 'Backslash', body: 'A `x_y\\` then 2*' } })
assert.deepEqual(codeText(backslashInSpan), ['x_y\\'], 'a backslash before a closing backtick is literal inside a span')
assert.ok(backslashInSpan.includes('"example-invented">2*</span>'))

const LINK_URL = 'https://example.test/a_b?q=c_d'
const hrefsOf = (html: string) => [...html.matchAll(/href="([^"]*)"/g)].map((m) => m[1])
const linkBody = render({ details: { title: 'Links', body: `See [the_report](${LINK_URL}) and <${LINK_URL}> but plain_name stays guarded` } })
assert.deepEqual(hrefsOf(linkBody), [LINK_URL])
assert.ok(linkBody.includes(`&lt;${LINK_URL}&gt;`), 'an autolink keeps its underscores verbatim')
assert.ok(linkBody.includes('the_' + ZWSP + 'report') || linkBody.includes('the_report'), 'the link text still renders')
assert.ok(linkBody.includes('plain_' + ZWSP + 'name'), 'prose underscores outside the links keep the guard')
const linkState = render({ before: `[report_one](${LINK_URL}) 4*`, steps: [`[report_two](${LINK_URL})`], after: `✓ [report_three](${LINK_URL}) 5*` })
assert.equal(hrefsOf(linkState).length, 3)
assert.ok(hrefsOf(linkState).every((href) => href === LINK_URL), 'a data-state link destination keeps its underscores')
for (const text of ['report_one', 'report_two', 'report_three']) assert.ok(linkState.includes(text.replace('_', '_' + ZWSP)) || linkState.includes(text), `${text} link text renders`)
assert.equal(countOf(linkState, /class="example-invented"/g), 2)
const parenLink = render({ details: { title: 'Links', body: '[w](https://example.test/a_(b_c)) a_b' } })
assert.deepEqual(hrefsOf(parenLink), ['https://example.test/a_(b_c)'])
const linkThenValue = render({ details: { title: 'Links', body: '[w_x](https://example.test/x_y) then 4* and b_c' } })
assert.deepEqual(hrefsOf(linkThenValue), ['https://example.test/x_y'])
assert.equal(countOf(linkThenValue, /class="example-invented"/g), 1)
assert.ok(linkThenValue.includes('b_' + ZWSP + 'c'))

const spacedLinks = '](' .repeat(20_000)
const linkStartedAt = performance.now()
render({ details: { title: 'Long', body: `${spacedLinks}\n\n${'<a:'.repeat(20_000)}\n\n${'\\`'.repeat(20_000)}\n\n${'`a``b```'.repeat(5_000)}` } })
assert.ok(performance.now() - linkStartedAt < 1500, 'link targets and escaped backticks must stay linear-time')

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
