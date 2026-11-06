import { useId, useMemo, useState, type FormEvent } from 'react'
import type { Draft, Step } from '../types'
import { pickDraft, restorePick } from './draft'
import { CommentField, FormError, StepFrame, SubmitButton, Tag, blockAttrs, useDraftSync, type ViewProps } from './common'
import { stripRecommended } from '../format'

type HandOffStep = Extract<Step, { kind: 'hand-off' }>

export function HandOffView({ step, changed, draft, actions }: ViewProps<HandOffStep>) {
  const name = useId()
  const [pick, setPick] = useState(() => restorePick(draft, step.choices.map((item) => item.id)))
  const [comment, setComment] = useState(typeof draft?.comment === 'string' ? draft.comment : '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  useDraftSync(step.id, useMemo<Draft>(() => pickDraft(pick, comment), [pick, comment]), actions)

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault()
    if (!pick) {
      setError('Pick how to continue first.')
      return
    }
    setError(null)
    setBusy(true)
    const payload: Record<string, unknown> = { pick }
    if (comment.trim()) payload.comment = comment
    if ((await actions.submit(payload)) === 'error') {
      setBusy(false)
      setError('Could not send your pick. Check the connection and try again.')
    }
  }

  return (
    <StepFrame step={step} changed={changed}>
      <form onSubmit={onSubmit} noValidate>
        <fieldset className="choice-list">
          <legend className="visually-hidden">How to continue</legend>
          {step.choices.map((choice) => {
            const inputId = `${name}-${choice.id}`
            return (
              <div key={choice.id} className="option-card" data-recommended={choice.recommended || undefined} {...blockAttrs(`choice:${choice.id}`, changed)}>
                <label htmlFor={inputId} className="option-pick">
                  <input id={inputId} type="radio" name={name} value={choice.id} checked={pick === choice.id} onChange={() => setPick(choice.id)} />
                  <span className="option-text">
                    <span className="option-label">
                      {stripRecommended(choice.label)}
                      {choice.recommended ? <>{' '}<Tag>Recommended</Tag></> : null}
                    </span>
                    <span className="option-description">{choice.description}</span>
                  </span>
                </label>
              </div>
            )
          })}
        </fieldset>
        <CommentField value={comment} onChange={setComment} />
        <FormError message={error} />
        <div className="actions">
          <SubmitButton label="Continue" busy={busy} />
        </div>
      </form>
    </StepFrame>
  )
}
