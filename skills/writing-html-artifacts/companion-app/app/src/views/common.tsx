import { useEffect, useId, useRef, type ReactNode } from 'react'
import { Button } from '@astryxdesign/core/Button'
import { AgentHtml, Md, blockKey } from '../blocks'
import type { Actions, Draft, Step } from '../types'
import { createDraftGate } from './draft'

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

/**
 * Posts the draft of step `stepId` 500 ms after its content last changed. The first render is the restored
 * state and posts nothing, and a value equal in content to the last one posted is never posted again, so a
 * new snapshot that merely rebuilds the same form does not loop.
 */
export function useDraftSync(stepId: string, value: Draft, actions: Actions): void {
  const gate = useRef(createDraftGate())
  useEffect(() => {
    if (!gate.current.wants(stepId, value)) return undefined
    const timer = setTimeout(() => {
      gate.current.sent(stepId, value)
      void actions.saveDraft(stepId, value as Record<string, unknown>)
    }, 500)
    return () => clearTimeout(timer)
  }, [stepId, value, actions])
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
