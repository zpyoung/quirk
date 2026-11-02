import { useState, type FormEvent } from 'react'
import { Button } from '@astryxdesign/core/Button'
import { STAGES, STAGE_LABELS, type Actions, type Decision, type StageId, type StageState } from './types'

function stateOf(stages: StageState[], id: StageId): StageState['state'] {
  return stages.find((s) => s.id === id)?.state ?? 'todo'
}

export function statusText(status: Decision['status']): string | null {
  if (status === 'assumed') return 'assumed, fast-tracked'
  if (status === 'open') return 'open'
  return null
}

export function Rail({ stages, openStage, onOpen }: { stages: StageState[]; openStage: StageId | null; onOpen(stage: StageId): void }) {
  return (
    <nav className="rail" aria-label="Brainstorm stages">
      <ol>
        {STAGES.map((id) => {
          const state = stateOf(stages, id)
          const label = STAGE_LABELS[id]
          return (
            <li key={id} className="rail-item" data-state={state}>
              {state === 'done' ? (
                <button type="button" className="rail-button" aria-pressed={openStage === id} onClick={() => onOpen(id)}>
                  <span className="rail-mark" aria-hidden="true">
                    ✓
                  </span>
                  {label}
                  <span className="sr-only"> (done, open recap)</span>
                </button>
              ) : (
                <span className="rail-label" aria-current={state === 'current' ? 'step' : undefined}>
                  <span className="rail-mark" aria-hidden="true">
                    {state === 'current' ? '●' : '○'}
                  </span>
                  {label}
                  {state === 'current' ? <span className="sr-only"> (current)</span> : null}
                </span>
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}

function ChangeForm({ decision, actions, onDone }: { decision: Decision; actions: Actions; onDone(sent: boolean): void }) {
  const [to, setTo] = useState('')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!to.trim()) {
      setError('Enter the new value.')
      return
    }
    setBusy(true)
    setError(null)
    const payload: Record<string, unknown> = { decision_id: decision.id, to }
    if (note.trim()) payload.note = note
    const result = await actions.send('edit-request', payload)
    setBusy(false)
    if (result === 'error') setError('Could not send the change. Try again.')
    else onDone(true)
  }

  return (
    <form className="change-form" onSubmit={submit} noValidate>
      <div className="field">
        <label htmlFor={`to-${decision.id}`}>New value</label>
        <input id={`to-${decision.id}`} type="text" value={to} onChange={(e) => setTo(e.target.value)} />
      </div>
      <div className="field">
        <label htmlFor={`note-${decision.id}`}>Note (optional)</label>
        <textarea id={`note-${decision.id}`} rows={2} value={note} onChange={(e) => setNote(e.target.value)} />
      </div>
      <p className="form-error" role="alert" hidden={!error}>
        {error}
      </p>
      <div className="actions">
        <Button type="submit" variant="primary" size="sm" label="Request change" isDisabled={busy} />
        <Button type="button" variant="secondary" size="sm" label="Cancel" onClick={() => onDone(false)} />
      </div>
    </form>
  )
}

/** The recap of one finished stage: its decisions, each with a Change control that opens an inline form. */
export function Recap({ stage, decisions, actions, onClose }: { stage: StageId; decisions: Decision[]; actions: Actions; onClose(): void }) {
  const [editing, setEditing] = useState<string | null>(null)
  const [requested, setRequested] = useState<Set<string>>(() => new Set())
  const items = decisions.filter((d) => d.stage === stage)

  return (
    <section className="recap" aria-labelledby="recap-title">
      <h1 id="recap-title" className="step-title">
        {STAGE_LABELS[stage]} recap
      </h1>
      {items.length ? (
        <ul className="recap-list">
          {items.map((decision) => (
            <li key={decision.id} className="recap-item" data-decision-id={decision.id}>
              <p className="recap-label">{decision.label}</p>
              <p className="recap-value">{decision.value}</p>
              {statusText(decision.status) ? <p className="muted">{statusText(decision.status)}</p> : null}
              {decision.note ? <p className="muted">{decision.note}</p> : null}
              {editing === decision.id ? (
                <ChangeForm
                  decision={decision}
                  actions={actions}
                  onDone={(sent) => {
                    setEditing(null)
                    if (sent) setRequested((prev) => new Set(prev).add(decision.id))
                  }}
                />
              ) : (
                <div className="actions">
                  <button type="button" className="link-button" onClick={() => setEditing(decision.id)}>
                    Change
                    <span className="sr-only"> {decision.label}</span>
                  </button>
                  {requested.has(decision.id) ? <span className="muted">Change requested</span> : null}
                </div>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">No decisions were recorded for this stage.</p>
      )}
      <div className="actions">
        <Button type="button" variant="secondary" label="Back to current step" onClick={onClose} />
      </div>
    </section>
  )
}
