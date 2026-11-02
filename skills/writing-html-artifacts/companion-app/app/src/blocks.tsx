import { createContext, memo, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { kitAssets, kitNeeds, loadAssets, mermaidAssets } from './libs'
import { renderMarkdown } from './markdown'

const isBrowser = typeof document !== 'undefined'

/** Whether the kit libraries the current step needs have finished loading; true when the step needs none. */
const KitReady = createContext(true)

export function KitProvider({ htmlParts, children }: { htmlParts: string[]; children: ReactNode }) {
  const joined = htmlParts.join('\n')
  const needs = kitNeeds(joined)
  const needsKit = needs.kit
  const [readyFor, setReadyFor] = useState('')
  const signature = needsKit ? [needs.chartjs, needs.highlightjs, needs.flow].join() : ''

  useEffect(() => {
    if (!needsKit) return undefined
    let cancelled = false
    const settle = () => {
      if (!cancelled) setReadyFor(signature)
    }
    loadAssets(kitAssets(needs)).then(settle, settle)
    return () => {
      cancelled = true
    }
    // needs is derived from signature
  }, [needsKit, signature])

  const ready = !isBrowser || !needsKit || readyFor === signature
  return <KitReady.Provider value={ready}>{children}</KitReady.Provider>
}

export function blockKey(stepId: string, blockId: string): string {
  return `${stepId}::${blockId}`
}

/**
 * Mounts agent-authored HTML. Callers pass `key={blockKey(stepId, blockId)}`; React only writes the markup when
 * the string changes, so kit elements that build their own DOM are never re-rendered underneath.
 */
export const AgentHtml = memo(function AgentHtml({ html, className }: { html?: string; className?: string }) {
  const ready = useContext(KitReady)
  if (!html) return null
  const gated = !ready && kitNeeds(html).kit
  return <div className={className ? `agent-html ${className}` : 'agent-html'} dangerouslySetInnerHTML={{ __html: gated ? '' : html }} />
})

export function Md({ source, className }: { source?: string; className?: string }) {
  const html = renderMarkdown(source)
  if (!html) return null
  return <div className={className ? `md ${className}` : 'md'} dangerouslySetInnerHTML={{ __html: html }} />
}

interface MermaidApi {
  initialize(config: Record<string, unknown>): void
  run(options: { nodes: HTMLElement[] }): Promise<void>
}

function mermaidTheme(): 'dark' | 'default' {
  const root = document.documentElement
  const forced = root.dataset.theme
  if (forced === 'dark') return 'dark'
  if (forced === 'light') return 'default'
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'default'
}

/** Renders one Mermaid diagram into a node React never touches again, loading the library on first use. */
export function Diagram({ source }: { source?: string }) {
  const host = useRef<HTMLDivElement>(null)
  const [failed, setFailed] = useState(false)
  const [themeTick, setThemeTick] = useState(0)

  useEffect(() => {
    const onTheme = () => setThemeTick((n) => n + 1)
    document.addEventListener('quirk-theme', onTheme)
    return () => document.removeEventListener('quirk-theme', onTheme)
  }, [])

  useEffect(() => {
    const node = host.current
    if (!source || !node) return undefined
    let cancelled = false
    setFailed(false)
    loadAssets(mermaidAssets())
      .then(async () => {
        const mermaid = (window as unknown as { mermaid?: MermaidApi }).mermaid
        if (!mermaid || cancelled) throw new Error('mermaid unavailable')
        mermaid.initialize({ startOnLoad: false, securityLevel: 'strict', theme: mermaidTheme() })
        node.removeAttribute('data-processed')
        node.textContent = source
        await mermaid.run({ nodes: [node] })
      })
      .catch(() => {
        if (!cancelled) setFailed(true)
      })
    return () => {
      cancelled = true
    }
  }, [source, themeTick])

  if (!source) return null
  return (
    <figure className="diagram">
      <div ref={host} className="diagram-host" role="img" aria-label="Diagram" hidden={failed} />
      {failed ? <pre className="diagram-source">{source}</pre> : null}
    </figure>
  )
}
