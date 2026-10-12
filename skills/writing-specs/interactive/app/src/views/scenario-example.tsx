import type { ReactNode } from 'react'
import { Markdown, type MarkdownInlinePlugin } from '@astryxdesign/core/Markdown'
import { Text } from '@astryxdesign/core/Text'
import type { ScenarioExample } from '../spec-types'
import { useItemLinkPlugins } from './item-links'
import { OFFLINE_MARKDOWN_COMPONENTS } from './shared'

/** Stands in for an invented-value star while the parser runs, because Astryx pairs two trailing stars in one part as emphasis. */
const STAR = '\uE000'
const restoreStar = (text: string) => text.replaceAll(STAR, '*')

const INVENTED_SPAN = /[^\s\uE000]+\uE000(?=[\s,;:.)\]]|$)/g

/** Keeps an invented value styled when it sits inside a result or rejection phrase, which the parser would otherwise consume whole. */
function phrase(text: string, key: string, className: string): ReactNode {
  const parts: ReactNode[] = []
  let last = 0
  for (const m of text.matchAll(INVENTED_SPAN)) {
    if (m.index > last) parts.push(restoreStar(text.slice(last, m.index)))
    parts.push(<span key={`${key}-${m.index}`} className="example-invented">{restoreStar(m[0])}</span>)
    last = m.index + m[0].length
  }
  if (last < text.length) parts.push(restoreStar(text.slice(last)))
  return <span key={key} className={className}>{parts}</span>
}

/** Colours the marks the example text uses; the gap pattern must match the renderer's open-gap regex. */
export const exampleMarkPlugins: MarkdownInlinePlugin[] = [
  { pattern: /✓\s*[^;\n]+/g, render: (match, key) => phrase(match[0], String(key), 'example-result') },
  { pattern: /✗\s*[^;\n]+/g, render: (match, key) => phrase(match[0], String(key), 'example-rejection') },
  { pattern: /[^\s\uE000]+\uE000(?=[\s,;:.)\]]|$)/g, render: (match, key) => <span key={key} className="example-invented">{restoreStar(match[0])}</span> },
  { pattern: /\[ASK: [^\[\]\n]+\]/g, render: (match, key) => <span key={key} className="example-gap">{restoreStar(match[0])}</span> },
]

const INVENTED_MARK = /([^\s*]+)\*(?=[\s,;:.)\]]|$)/g

// SpecMarkdown takes no extra plugins, so this repeats its underscore guard to keep prose underscores from becoming emphasis.
function ExampleMarkdown({ children, hasLineBreaks }: { children: string; hasLineBreaks?: boolean }) {
  const itemLinkPlugins = useItemLinkPlugins()
  const text = children.replace(/_/g, '_​').replace(INVENTED_MARK, `$1${STAR}`)
  return (
    <Markdown
      components={OFFLINE_MARKDOWN_COMPONENTS}
      inlinePlugins={[...(itemLinkPlugins ?? []), ...exampleMarkPlugins]}
      contentWidth="100%"
      density="compact"
    >
      {hasLineBreaks ? text.replace(/\n/g, '  \n') : text}
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
