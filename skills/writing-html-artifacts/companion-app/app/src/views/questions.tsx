import { useId, useMemo, useState, type FormEvent } from 'react'
import { AgentHtml, Diagram, blockKey } from '../blocks'
import type { AnswerState, Draft, Question, Step } from '../types'
import { CommentField, FormError, StepFrame, SubmitButton, Tag, blockAttrs, useDraftSync, type ViewProps } from './common'

type QuestionsStep = Extract<Step, { kind: 'questions' }>

interface FormState {
  answers: Record<string, AnswerState>
  comment: string
}

/** The recommended option first, then the rest in authored order; never selected for the user. */
export function orderedOptions(question: Question) {
  const options = question.options ?? []
  if (!question.recommended) return options
  return [...options.filter((o) => o.id === question.recommended), ...options.filter((o) => o.id !== question.recommended)]
}

function restore(step: QuestionsStep, draft: Draft | null | undefined): FormState {
  const answers: Record<string, AnswerState> = {}
  for (const question of step.questions) {
    const saved = draft?.answers?.[question.id]
    if (saved && typeof saved === 'object') answers[question.id] = { ...saved }
  }
  return { answers, comment: typeof draft?.comment === 'string' ? draft.comment : '' }
}

function isAnswered(answer: AnswerState | undefined): boolean {
  if (!answer) return false
  if (answer.skipped) return true
  return Boolean(answer.selected?.length || answer.other?.trim() || answer.text?.trim())
}

/** Draft keeps typed values even on a skipped question; a submit sends a skip as just `skipped: true`. */
function serialize(step: QuestionsStep, state: FormState, forSubmit: boolean): Record<string, AnswerState> {
  const out: Record<string, AnswerState> = {}
  for (const question of step.questions) {
    const answer = state.answers[question.id]
    if (!answer) continue
    if (answer.skipped && forSubmit) {
      out[question.id] = { skipped: true }
      continue
    }
    const entry: AnswerState = {}
    if (question.type === 'text') {
      if (answer.text) entry.text = answer.text
    } else {
      if (answer.selected?.length) entry.selected = answer.selected
      if (answer.other) entry.other = answer.other
    }
    if (answer.skipped) entry.skipped = true
    if (Object.keys(entry).length) out[question.id] = entry
  }
  return out
}

export function QuestionsView({ step, changed, draft, actions }: ViewProps<QuestionsStep>) {
  const [state, setState] = useState<FormState>(() => restore(step, draft))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const draftValue = useMemo<Draft>(
    () => ({ answers: serialize(step, state, false), comment: state.comment }),
    [step, state],
  )
  useDraftSync(step.id, draftValue, actions)

  const patch = (qid: string, next: Partial<AnswerState> | ((a: AnswerState) => AnswerState)) =>
    setState((s) => {
      const current = s.answers[qid] ?? {}
      const updated = typeof next === 'function' ? next(current) : { ...current, ...next }
      return { ...s, answers: { ...s.answers, [qid]: updated } }
    })

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault()
    const missing = step.questions.filter((q) => !isAnswered(state.answers[q.id]))
    if (missing.length) {
      setError(`Answer or skip: ${missing.map((q) => q.prompt).join('; ')}`)
      return
    }
    setError(null)
    setBusy(true)
    const payload: Record<string, unknown> = { answers: serialize(step, state, true) }
    if (state.comment.trim()) payload.comment = state.comment
    const result = await actions.submit(payload)
    if (result === 'error') {
      setBusy(false)
      setError('Could not send your answers. Check the connection and try again.')
    }
  }

  return (
    <StepFrame step={step} changed={changed}>
      <form className="question-form" onSubmit={onSubmit} noValidate>
        {step.questions.map((question) => (
          <QuestionBlock
            key={question.id}
            stepId={step.id}
            question={question}
            answer={state.answers[question.id]}
            changed={changed}
            patch={(next) => patch(question.id, next)}
          />
        ))}
        <CommentField value={state.comment} onChange={(comment) => setState((s) => ({ ...s, comment }))} label="Comment on this batch (optional)" />
        <FormError message={error} />
        <div className="actions">
          <SubmitButton label="Submit answers" busy={busy} />
        </div>
      </form>
    </StepFrame>
  )
}

interface QuestionBlockProps {
  stepId: string
  question: Question
  answer: AnswerState | undefined
  changed: Set<string>
  patch(next: Partial<AnswerState> | ((a: AnswerState) => AnswerState)): void
}

function QuestionBlock({ stepId, question, answer, changed, patch }: QuestionBlockProps) {
  const uid = useId()
  const skipped = Boolean(answer?.skipped)
  const selected = answer?.selected ?? []
  const options = orderedOptions(question)
  const name = `${uid}-${question.id}`

  const toggle = (oid: string) =>
    patch((a) => {
      const current = a.selected ?? []
      if (question.type === 'single') return { ...a, selected: [oid], other: '' }
      return { ...a, selected: current.includes(oid) ? current.filter((id) => id !== oid) : [...current, oid] }
    })

  return (
    <div className="question" data-skipped={skipped || undefined} {...blockAttrs(`question:${question.id}`, changed)}>
      <fieldset disabled={skipped}>
      <legend>
        {question.header ? <span className="question-header">{question.header}</span> : null}
        <span className="question-prompt">{question.prompt}</span>
      </legend>
      <AgentHtml key={blockKey(stepId, `content:${question.id}`)} html={question.content_html} />
      {question.diagram ? <Diagram key={blockKey(stepId, `diagram:${question.id}`)} source={question.diagram} /> : null}
      {question.type === 'text' ? (
        <div className="field">
          <label htmlFor={`${name}-text`}>Your answer</label>
          <textarea id={`${name}-text`} rows={3} value={answer?.text ?? ''} onChange={(e) => patch({ text: e.target.value })} />
        </div>
      ) : (
        <>
          <div className="options">
            {options.map((option) => {
              const inputId = `${name}-${option.id}`
              const recommended = option.id === question.recommended
              return (
                <div key={option.id} className="option-card" {...blockAttrs(`option:${question.id}/${option.id}`, changed)}>
                  <label htmlFor={inputId} className="option-pick">
                    <input
                      id={inputId}
                      type={question.type === 'single' ? 'radio' : 'checkbox'}
                      name={name}
                      value={option.id}
                      checked={selected.includes(option.id)}
                      onChange={() => toggle(option.id)}
                    />
                    <span className="option-text">
                      <span className="option-label">
                        {option.label}
                        {recommended ? <>{' '}<Tag>(Recommended)</Tag></> : null}
                      </span>
                      {option.description ? <span className="option-description">{option.description}</span> : null}
                    </span>
                  </label>
                  <AgentHtml key={blockKey(stepId, `preview:${question.id}/${option.id}`)} html={option.preview_html} className="option-preview" />
                </div>
              )
            })}
          </div>
          <div className="field other-field">
            <label htmlFor={`${name}-other`}>Other</label>
            <input
              id={`${name}-other`}
              type="text"
              value={answer?.other ?? ''}
              onChange={(e) =>
                patch((a) => ({ ...a, other: e.target.value, selected: question.type === 'single' && e.target.value ? [] : a.selected }))
              }
            />
          </div>
        </>
      )}
      </fieldset>
      <div className="question-tools">
        <button
          type="button"
          className="link-button"
          aria-pressed={skipped}
          onClick={() => patch((a) => ({ ...a, skipped: a.skipped ? undefined : true }))}
        >
          {skipped ? 'Undo skip' : 'Skip'}
        </button>
      </div>
    </div>
  )
}
