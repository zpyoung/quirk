import { useId, useMemo, useState, type FormEvent } from 'react'
import { AgentHtml, Md, blockKey } from '../blocks'
import type { Draft, Step } from '../types'
import { pickDraft, restorePick } from './draft'
import { CommentField, FormError, StepFrame, SubmitButton, Tag, blockAttrs, useDraftSync, type ViewProps } from './common'

type ApproachesStep = Extract<Step, { kind: 'approaches' }>

export function ApproachesView({ step, changed, draft, actions }: ViewProps<ApproachesStep>) {
  const name = useId()
  const [pick, setPick] = useState(() => restorePick(draft, step.approaches.map((item) => item.id)))
  const [comment, setComment] = useState(typeof draft?.comment === 'string' ? draft.comment : '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  useDraftSync(step.id, useMemo<Draft>(() => pickDraft(pick, comment), [pick, comment]), actions)

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault()
    if (!pick) {
      setError('Pick an approach first.')
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
        <fieldset className="approach-grid">
          <legend className="visually-hidden">Approaches</legend>
          {step.approaches.map((approach) => {
            const inputId = `${name}-${approach.id}`
            return (
              <div key={approach.id} className="approach-card" data-recommended={approach.recommended || undefined} {...blockAttrs(`approach:${approach.id}`, changed)}>
                <label htmlFor={inputId} className="approach-pick">
                  <input id={inputId} type="radio" name={name} value={approach.id} checked={pick === approach.id} onChange={() => setPick(approach.id)} />
                  <span className="approach-title">{approach.title}</span>
                  {approach.recommended ? <Tag>Recommended</Tag> : null}
                </label>
                <Md source={approach.summary_md} className="approach-summary" />
                {approach.pros?.length ? (
                  <section aria-label={`Pros of ${approach.title}`}>
                    <h3 className="mini-heading">Pros</h3>
                    <ul className="pros">
                      {approach.pros.map((item, i) => (
                        <li key={i}>{item}</li>
                      ))}
                    </ul>
                  </section>
                ) : null}
                {approach.cons?.length ? (
                  <section aria-label={`Cons of ${approach.title}`}>
                    <h3 className="mini-heading">Cons</h3>
                    <ul className="cons">
                      {approach.cons.map((item, i) => (
                        <li key={i}>{item}</li>
                      ))}
                    </ul>
                  </section>
                ) : null}
                <AgentHtml key={blockKey(step.id, `content:${approach.id}`)} html={approach.content_html} />
                {approach.sources?.length ? (
                  <section aria-label={`Sources for ${approach.title}`}>
                    <h3 className="mini-heading">Sources</h3>
                    <ul className="sources">
                      {approach.sources.map((source, i) => (
                        <li key={i}>
                          {/^https?:\/\//i.test(source.url) ? (
                            <a href={source.url} target="_blank" rel="noreferrer">
                              {source.title}
                            </a>
                          ) : (
                            source.title
                          )}
                        </li>
                      ))}
                    </ul>
                  </section>
                ) : null}
              </div>
            )
          })}
        </fieldset>
        <CommentField value={comment} onChange={setComment} />
        <FormError message={error} />
        <div className="actions">
          <SubmitButton label="Submit pick" busy={busy} />
        </div>
      </form>
    </StepFrame>
  )
}
