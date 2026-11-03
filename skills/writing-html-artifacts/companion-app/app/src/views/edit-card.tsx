import { useState } from 'react'
import { Button } from '@astryxdesign/core/Button'
import type { Step } from '../types'
import { FormError, StepFrame, type ViewProps } from './common'

type EditCardStep = Extract<Step, { kind: 'edit-card' }>

export function EditCardView({ step, changed, actions }: ViewProps<EditCardStep>) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const decide = async (decision: 'confirm' | 'cancel') => {
    setBusy(true)
    setError(null)
    if ((await actions.send('edit-decision', { decision }, true)) === 'error') {
      setBusy(false)
      setError('Could not send your decision. Check the connection and try again.')
    }
  }

  return (
    <StepFrame step={step} changed={changed}>
      <div className="edit-card">
        <p className="edit-change">
          <span className="edit-from">{step.from}</span>
          <span aria-hidden="true"> → </span>
          <span className="sr-only"> changes to </span>
          <span className="edit-to">{step.to}</span>
        </p>
        <h2 className="mini-heading">This invalidates</h2>
        {step.invalidates.length ? (
          <ul className="invalidates">
            {step.invalidates.map((item, i) => (
              <li key={`${item.step_id ?? item.label}-${i}`}>{item.label}</li>
            ))}
          </ul>
        ) : (
          <p className="muted">Nothing else needs to be redone.</p>
        )}
        <FormError message={error} />
        <div className="actions">
          <Button type="button" variant="primary" label="Confirm and redo" isDisabled={busy} onClick={() => void decide('confirm')} />
          <Button type="button" variant="secondary" label="Cancel" isDisabled={busy} onClick={() => void decide('cancel')} />
        </div>
      </div>
    </StepFrame>
  )
}
