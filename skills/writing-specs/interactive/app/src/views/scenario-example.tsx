import React, { type ReactNode } from 'react'
import { Markdown, type MarkdownInlinePlugin } from '@astryxdesign/core/Markdown'
import { Text } from '@astryxdesign/core/Text'
import type { ScenarioExample } from '../spec-types'
import { useItemLinkPlugins } from './item-links'
import { OFFLINE_MARKDOWN_COMPONENTS } from './shared'

/** Stands in for an invented-value star while the parser runs, because Astryx pairs two trailing stars in one part as emphasis. */
const STAR = '\uE000'
/** Takes the place of a literal U+E000 in the text, so only a swapped star ever reads as the placeholder. */
const LITERAL_STAR_SENTINEL = '\uE001'
const restoreStar = (text: string) => text.replaceAll(STAR, '*').replaceAll(LITERAL_STAR_SENTINEL, STAR)

/** A result or rejection phrase: its mark plus everything up to the next semicolon or line end. */
export const EXAMPLE_PHRASE = /([✓✗])([^;\n]+)/g

/** Invented-value runs start at a whitespace boundary so each position of a long run without a star fails in constant time. */
const INVENTED_MARK = /(?<![^\s])([^\s*]+)\*(?=[\s,;:.)\]]|$)/g

/** Colours the marks that survive Markdown parsing; the gap pattern must match the renderer's open-gap regex. */
export const exampleMarkPlugins: MarkdownInlinePlugin[] = [
  { pattern: /(?<![^\s])[^\s\uE000]+\uE000(?=[\s,;:.)\]]|$)/g, render: (match, key) => <span key={key} className="example-invented">{restoreStar(match[0])}</span> },
  { pattern: /\[ASK: [^\[\]\n]+\]/g, render: (match, key) => <span key={key} className="example-gap">{restoreStar(match[0])}</span> },
]

/** Last in the plugin order so it only sees placeholders the marks above left in plain text. */
const restorePlaceholders: MarkdownInlinePlugin = {
  pattern: /[\uE000\uE001]/g,
  render: (match, key) => <React.Fragment key={key}>{restoreStar(match[0])}</React.Fragment>,
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
  const text = children.replace(/_/g, '_​').replaceAll(STAR, LITERAL_STAR_SENTINEL).replace(INVENTED_MARK, `$1${STAR}`)
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

function ExamplePane({ label, className, children }: { label: string; className?: string; children: ReactNode }) {
  return (
    <section className={`example-pane${className ? ` ${className}` : ''}`} aria-label={label}>
      <Text type="label" color="secondary">{label}</Text>
      {children}
    </section>
  )
}

/** A scenario's worked example as three panes: the records before, the steps that happen, the records after. */
export function ScenarioExampleView({ example }: { example: ScenarioExample }) {
  return (
    <div className="scenario-example">
      <ExamplePane label="Data before" className="example-before">
        <ExampleMarkdown hasLineBreaks>{example.before}</ExampleMarkdown>
      </ExamplePane>
      <ExamplePane label="Walkthrough">
        <ol>
          {example.steps.map((step, i) => (
            <li key={i}><ExampleMarkdown>{step}</ExampleMarkdown></li>
          ))}
        </ol>
      </ExamplePane>
      <ExamplePane label="Data after" className="example-after">
        <ExampleMarkdown hasLineBreaks>{example.after}</ExampleMarkdown>
      </ExamplePane>
    </div>
  )
}
