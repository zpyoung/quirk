import { useEffect, useId, useRef, type ReactNode } from 'react'
import { Button } from '@astryxdesign/core/Button'
import { AgentHtml, Md, blockKey } from '../blocks'
import type { Actions, Draft, Step } from '../types'

export interface ViewProps<S extends Step = Step> {
  step: S
  changed: Set<string>
  draft: Draft | null | undefined
  actions: Actions
  token: string
}

/** Attributes for a commentable block: its stable id, plus a marker when the latest revision changed it. */
export function blockAttrs(id: string, changed: Set<string>): { 'data-block-id': string; 'data-changed'?: 'true' } {
  return changed.has(id) ? { 'data-block-id': id, 'data-changed': 'true' } : { 'data-block-id': id }
}

export function StepFrame({ step, changed, children }: { step: Step; changed: Set<string>; children: ReactNode }) {
  return (
    <article className="step" data-step-kind={step.kind} data-step-id={step.id}>
      <header className="step-head">
        <h1 className="step-title">{step.title}</h1>
        {step.changed?.summary ? (
          <p className="changed-banner">
            <strong>What changed:</strong> {step.changed.summary}
          </p>
        ) : null}
        <Md source={step.intro_md} className="step-intro" />
        <AgentHtml key={blockKey(step.id, 'intro_html')} html={step.intro_html} className="step-intro" />
      </header>
      <div data-changed-count={changed.size || undefined}>{children}</div>
    </article>
  )
}

/** Posts the draft 500 ms after the last change; the first render is the restored state, so it posts nothing. */
export function useDraftSync(value: Draft, actions: Actions): void {
  const first = useRef(true)
  useEffect(() => {
    if (first.current) {
      first.current = false
      return undefined
    }
    const timer = setTimeout(() => void actions.send('draft', value as Record<string, unknown>), 500)
    return () => clearTimeout(timer)
  }, [value, actions])
}

export function CommentField({ value, onChange, label = 'Comment (optional)' }: { value: string; onChange(next: string): void; label?: string }) {
  const id = useId()
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <textarea id={id} rows={3} value={value} onChange={(event) => onChange(event.target.value)} />
    </div>
  )
}

export function FormError({ message }: { message: string | null }) {
  return (
    <p className="form-error" role="alert" hidden={!message}>
      {message}
    </p>
  )
}

export function SubmitButton({ label, busy, disabled }: { label: string; busy: boolean; disabled?: boolean }) {
  return <Button type="submit" variant="primary" label={label} isDisabled={busy || disabled} />
}

export function Tag({ children, tone = 'accent' }: { children: ReactNode; tone?: 'accent' | 'muted' | 'warn' }) {
  return <span className={`tag tag-${tone}`}>{children}</span>
}
