import React, { type ReactNode } from 'react'
import { Markdown, type MarkdownInlinePlugin } from '@astryxdesign/core/Markdown'
import { Text } from '@astryxdesign/core/Text'
import type { ScenarioDetails, ScenarioExample } from '../spec-types'
import { useItemLinkPlugins } from './item-links'
import { OFFLINE_MARKDOWN_COMPONENTS } from './shared'

/** Stands in for an invented-value star while the parser runs, because Astryx pairs two trailing stars in one part as emphasis. */
const STAR = '\uE000'
/** Takes the place of a literal U+E000 in the text, so only a swapped star ever reads as the placeholder. */
const LITERAL_STAR_SENTINEL = '\uE001'
const restoreStar = (text: string) => text.replaceAll(STAR, '*').replaceAll(LITERAL_STAR_SENTINEL, STAR)

/** A result or rejection phrase: its mark plus everything up to the next semicolon or line end. */
export const EXAMPLE_PHRASE = /([✓✗])([^;\n]+)/g

/** Invented-value runs start at whitespace or right after a previous value's `*,`, so each position of a long run without a star fails in constant time. */
const INVENTED_MARK = /(?<=^|\s|\*,)([^\s*]+)\*(?=[\s,;:.)\]]|$)/g

/** Colours the marks that survive Markdown parsing; the gap pattern must match the renderer's open-gap regex. */
export const exampleMarkPlugins: MarkdownInlinePlugin[] = [
  { pattern: /(?<=^|\s|\uE000,)[^\s\uE000]+\uE000(?=[\s,;:.)\]]|$)/g, render: (match, key) => <span key={key} className="example-invented">{restoreStar(match[0])}</span> },
  { pattern: /\[ASK: [^\[\]\n]+\]/g, render: (match, key) => <span key={key} className="example-gap">{restoreStar(match[0])}</span> },
]

/** Last in the plugin order so it only sees placeholders the marks above left in plain text. */
const restorePlaceholders: MarkdownInlinePlugin = {
  pattern: /[\uE000\uE001]/g,
  render: (match, key) => <React.Fragment key={key}>{restoreStar(match[0])}</React.Fragment>,
}

/** Colours a result or rejection phrase inside one text node of the details body; nested values and gaps keep their own marks. */
export const EXAMPLE_PHRASE_PLUGIN: MarkdownInlinePlugin = {
  pattern: /[✓✗][^;\n]+/g,
  render: (match, key) => (
    <span key={key} className={match[0][0] === '✓' ? 'example-result' : 'example-rejection'}>
      {renderNestedMarks(match[0])}
    </span>
  ),
}

/** Splits phrase text on the same patterns exampleMarkPlugins use, so a value or gap inside a phrase gets its own span. */
function renderNestedMarks(text: string): ReactNode[] {
  const [invented, gap] = exampleMarkPlugins.map((plugin) => plugin.pattern)
  const nested = new RegExp(`${invented.source}|${gap.source}`, 'g')
  const nodes: ReactNode[] = []
  let last = 0
  for (const m of text.matchAll(nested)) {
    if (m.index > last) nodes.push(restoreStar(text.slice(last, m.index)))
    nodes.push(<span key={m.index} className={m[0].startsWith('[ASK: ') ? 'example-gap' : 'example-invented'}>{restoreStar(m[0])}</span>)
    last = m.index + m[0].length
  }
  if (last < text.length) nodes.push(restoreStar(text.slice(last)))
  return nodes
}

type Segment = { text: string; className?: string }

/** Cuts one line into plain stretches and ✓/✗ phrases so a phrase can be parsed whole, nested marks included. */
function segmentLine(line: string): Segment[] {
  const segments: Segment[] = []
  let last = 0
  for (const m of line.matchAll(EXAMPLE_PHRASE)) {
    if (m.index > last) segments.push({ text: line.slice(last, m.index) })
    segments.push({ text: m[0], className: m[1] === '✓' ? 'example-result' : 'example-rejection' })
    last = m.index + m[0].length
  }
  if (last < line.length) segments.push({ text: line.slice(last) })
  return segments
}

// SpecMarkdown takes no extra plugins, so this repeats its underscore guard to keep prose underscores from becoming emphasis.
function ExampleMarkdown({ children, hasLineBreaks }: { children: string; hasLineBreaks?: boolean }) {
  const itemLinkPlugins = useItemLinkPlugins()
  const inlinePlugins = [...(itemLinkPlugins ?? []), ...exampleMarkPlugins, restorePlaceholders]
  const text = children.replace(/\r\n?/g, '\n').replace(/_/g, '_​').replaceAll(STAR, LITERAL_STAR_SENTINEL).replace(INVENTED_MARK, `$1${STAR}`)
  if (!new RegExp(EXAMPLE_PHRASE.source).test(text)) {
    return (
      <Markdown components={OFFLINE_MARKDOWN_COMPONENTS} inlinePlugins={inlinePlugins} contentWidth="100%" density="compact">
        {hasLineBreaks ? text.replace(/\n/g, '  \n') : text}
      </Markdown>
    )
  }
  const inline = (content: string, key: string) => (
    <Markdown key={key} display="inline" components={OFFLINE_MARKDOWN_COMPONENTS} inlinePlugins={inlinePlugins} density="compact">
      {content}
    </Markdown>
  )
  return (
    <div>
      {text.split('\n').map((line, lineIndex) => (
        <React.Fragment key={lineIndex}>
          {lineIndex > 0 && (hasLineBreaks ? <br /> : ' ')}
          {segmentLine(line).map((segment, i) => {
            const key = `${lineIndex}-${i}`
            const [, lead, core, trail] = /^(\s*)([\s\S]*?)(\s*)$/.exec(segment.text)!
            const body = core && (segment.className
              ? <span key={key} className={segment.className}>{inline(core, key)}</span>
              : inline(core, key))
            return <React.Fragment key={key}>{lead}{body}{trail}</React.Fragment>
          })}
        </React.Fragment>
      ))}
    </div>
  )
}

/** Underscore guard plus the invented-value star swap, for text that is not inside code. */
function guardProse(text: string): string {
  return text.replace(/_/g, '_\u200b').replaceAll(STAR, LITERAL_STAR_SENTINEL).replace(INVENTED_MARK, `$1${STAR}`)
}

/** Guards one stretch of prose that sits beside code, padding the edges the code touches so the star pattern's start and end anchors don't treat the code as the text's boundary. */
function guardProseBesideCode(text: string, afterCode: boolean, beforeCode: boolean): string {
  const guarded = guardProse(`${afterCode ? '\u0001' : ''}${text}${beforeCode ? '\u0001' : ''}`)
  return guarded.slice(afterCode ? 1 : 0, beforeCode ? -1 : undefined)
}

/** Guards one paragraph, leaving its inline code spans exactly as written. A run of N backticks opens a span that the next run of exactly N closes; an unmatched run is literal. */
function guardParagraph(paragraph: string): string {
  const runs = [...paragraph.matchAll(/`+/g)]
  const nextSameLength = new Array<number>(runs.length).fill(-1)
  const latestByLength = new Map<number, number>()
  for (let i = runs.length - 1; i >= 0; i--) {
    nextSameLength[i] = latestByLength.get(runs[i][0].length) ?? -1
    latestByLength.set(runs[i][0].length, i)
  }
  let out = ''
  let cursor = 0
  let i = 0
  while (i < runs.length) {
    const closer = nextSameLength[i]
    if (closer === -1) {
      i++
      continue
    }
    const spanEnd = runs[closer].index + runs[closer][0].length
    out += guardProseBesideCode(paragraph.slice(cursor, runs[i].index), cursor > 0, true) + paragraph.slice(runs[i].index, spanEnd)
    cursor = spanEnd
    i = closer + 1
  }
  return out + guardProseBesideCode(paragraph.slice(cursor), cursor > 0, false)
}

/** Guards prose outside code; a code span never reaches across a blank line. */
function guardProseOutsideCode(text: string): string {
  return text
    .split(/(\n[ \t]*\n)/)
    .map((part, i) => (i % 2 === 1 ? part : guardParagraph(part)))
    .join('')
}

const FENCE_LINE = /^[ \t]*(?:>[ \t]*)*(`{3,}|~{3,})(.*)$/

/** Normalizes line endings, then applies the guards to everything except fenced code blocks and inline code spans, which pass through as written. */
function prepareDetailsBody(body: string): string {
  const lines = body.replace(/\r\n?/g, '\n').match(/[^\n]*\n|[^\n]+/g) ?? []
  let out = ''
  let prose = ''
  let fence: { char: string; length: number } | null = null
  for (const line of lines) {
    const content = line.replace(/\n$/, '')
    const marker = FENCE_LINE.exec(content)
    if (fence) {
      out += line
      if (marker && marker[1][0] === fence.char && marker[1].length >= fence.length && marker[2].trim() === '') fence = null
      continue
    }
    if (marker && !(marker[1][0] === '`' && marker[2].includes('`'))) {
      out += guardProseOutsideCode(prose) + line
      prose = ''
      fence = { char: marker[1][0], length: marker[1].length }
      continue
    }
    prose += line
  }
  return out + guardProseOutsideCode(prose)
}

/** The details body as one block of Markdown, so tables, lists and code blocks keep their structure. */
function ExampleDetailsBody({ children }: { children: string }) {
  const itemLinkPlugins = useItemLinkPlugins()
  const inlinePlugins = [...(itemLinkPlugins ?? []), EXAMPLE_PHRASE_PLUGIN, ...exampleMarkPlugins, restorePlaceholders]
  return (
    <Markdown components={OFFLINE_MARKDOWN_COMPONENTS} inlinePlugins={inlinePlugins} contentWidth="100%" density="compact">
      {prepareDetailsBody(children)}
    </Markdown>
  )
}

function ExamplePane({ label, className, children }: { label: string; className?: string; children: ReactNode }) {
  return (
    <section className={`example-pane${className ? ` ${className}` : ''}`} aria-label={label}>
      <Text type="label" color="secondary">{label}</Text>
      {children}
    </section>
  )
}

/** A scenario's worked example: the data-state panes (records before, steps, records after) when it has them, then its titled details pane. */
export function ScenarioExampleView({ example }: { example: ScenarioExample }) {
  const { before, steps, after, details } = example
  return (
    <div className="scenario-example">
      {before !== undefined && steps !== undefined && after !== undefined && (
        <div className="example-grid">
          <ExamplePane label="Data before" className="example-before">
            <ExampleMarkdown hasLineBreaks>{before}</ExampleMarkdown>
          </ExamplePane>
          <ExamplePane label="Walkthrough">
            <ol>
              {steps.map((step, i) => (
                <li key={i}><ExampleMarkdown>{step}</ExampleMarkdown></li>
              ))}
            </ol>
          </ExamplePane>
          <ExamplePane label="Data after" className="example-after">
            <ExampleMarkdown hasLineBreaks>{after}</ExampleMarkdown>
          </ExamplePane>
        </div>
      )}
      {details && <ExampleDetails details={details} />}
    </div>
  )
}

function ExampleDetails({ details }: { details: ScenarioDetails }) {
  return (
    <ExamplePane label={details.title} className="example-details">
      <ExampleDetailsBody>{details.body}</ExampleDetailsBody>
    </ExamplePane>
  )
}
