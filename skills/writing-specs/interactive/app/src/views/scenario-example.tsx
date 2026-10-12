import type { ReactNode } from 'react'
import { Markdown, type MarkdownInlinePlugin } from '@astryxdesign/core/Markdown'
import { Text } from '@astryxdesign/core/Text'
import type { ScenarioExample } from '../spec-types'
import { useItemLinkPlugins } from './item-links'
import { OFFLINE_MARKDOWN_COMPONENTS } from './shared'

/** Colours the marks the example text uses; the gap pattern must match the renderer's open-gap regex. */
export const exampleMarkPlugins: MarkdownInlinePlugin[] = [
  { pattern: /✓\s*[^;\n]+/g, render: (match, key) => <span key={key} className="example-result">{match[0]}</span> },
  { pattern: /✗\s*[^;\n]+/g, render: (match, key) => <span key={key} className="example-rejection">{match[0]}</span> },
  { pattern: /[^\s*]+\*(?=[\s,;:.)\]]|$)/g, render: (match, key) => <span key={key} className="example-invented">{match[0]}</span> },
  { pattern: /\[ASK: [^\]\n]+\]/g, render: (match, key) => <span key={key} className="example-gap">{match[0]}</span> },
]

// SpecMarkdown takes no extra plugins, so this repeats its underscore guard to keep prose underscores from becoming emphasis.
function ExampleMarkdown({ children, hasLineBreaks }: { children: string; hasLineBreaks?: boolean }) {
  const itemLinkPlugins = useItemLinkPlugins()
  const text = children.replace(/_/g, '_​')
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
