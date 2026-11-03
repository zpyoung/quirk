import { useId, useState, type FormEvent, type JSX } from 'react'
import { Button } from '@astryxdesign/core/Button'
import type { Boot } from '../types'
import { postRunEvent } from './api'
import type { RunAnswer, RunQuestion } from './types'

type Status = 'idle' | 'sending' | 'sent' | 'error'

function answeredLine(answer: RunAnswer | undefined): string {
  if (!answer) return 'Already answered.'
  const what = answer.label ?? answer.text ?? answer.pick ?? ''
  const where = answer.source === 'orca' ? 'in orca ask' : answer.source === 'sdd' ? 'by SDD' : 'in the tab'
  return `Already answered ${where}: ${what}`
}

/** One open question: its options as radios plus an Other box; sends exactly one of a pick or typed text. */
export function QuestionCard(props: { question: RunQuestion; boot: Boot; onClose(): void }): JSX.Element {
  return <QuestionCardBody key={props.question.id} {...props} />
}

function QuestionCardBody({ question, boot, onClose }: { question: RunQuestion; boot: Boot; onClose(): void }): JSX.Element {
  const groupName = useId()
  const [pick, setPick] = useState<string | null>(null)
  const [text, setText] = useState('')
  const [status, setStatus] = useState<Status>('idle')
  const [lost, setLost] = useState<RunAnswer | null>(null)

  const closeButton = <Button type="button" variant="secondary" size="sm" label="Close" onClick={onClose} />
  const header = (
    <header className="run-card-head">
      {question.task ? <span className="run-card-task">{question.task}</span> : null}
      {question.header ? <span className="run-card-header">{question.header}</span> : null}
      {closeButton}
    </header>
  )

  if (question.state === 'answered' || lost) {
    return (
      <section className="run-card" aria-label="Question" data-run-part="question-card" data-question={question.id}>
        {header}
        <p className="run-card-prompt">{question.prompt}</p>
        <p className="run-card-note" role="status">
          {answeredLine(lost ?? question.answer)}
        </p>
      </section>
    )
  }

  const ordered = [...question.options].sort((a, b) => Number(b.value === question.recommended) - Number(a.value === question.recommended))
  const typed = text.trim()
  const locked = status === 'sending' || status === 'sent'
  const canSend = !locked && (pick !== null || typed !== '')

  const send = async (event: FormEvent) => {
    event.preventDefault()
    if (!canSend) return
    setStatus('sending')
    const payload = pick !== null ? { question: question.id, pick } : { question: question.id, text: typed }
    const result = await postRunEvent(boot, 'run-answer', payload)
    if (result.kind === 'ok' || result.kind === 'duplicate') setStatus('sent')
    else if (result.kind === 'answered') setLost(result.answer)
    else setStatus('error')
  }

  return (
    <section className="run-card" aria-label="Question" data-run-part="question-card" data-question={question.id}>
      {header}
      <form onSubmit={send}>
        <fieldset className="run-card-fields" disabled={locked}>
          <legend className="run-card-prompt">{question.prompt}</legend>
          {ordered.map((option) => (
            <label key={option.value} className="run-card-option">
              <input
                type="radio"
                name={groupName}
                value={option.value}
                checked={pick === option.value}
                onChange={() => {
                  setPick(option.value)
                  setText('')
                }}
              />
              <span className="run-card-option-body">
                <span>
                  {option.label}
                  {option.value === question.recommended ? <span className="run-card-tag">Recommended</span> : null}
                </span>
                {option.description ? <span className="run-card-option-desc">{option.description}</span> : null}
              </span>
            </label>
          ))}
          <label className="run-card-other">
            <span>Other</span>
            <input
              type="text"
              value={text}
              onChange={(event) => {
                setText(event.target.value)
                if (event.target.value.trim() !== '') setPick(null)
              }}
            />
          </label>
        </fieldset>
        <Button type="submit" variant="primary" size="sm" label="Send" isDisabled={!canSend} />
        {status === 'sent' ? (
          <p className="run-card-note" role="status">
            Sent; waiting for SDD
          </p>
        ) : null}
        {status === 'error' ? (
          <p className="run-card-note" data-tone="error" role="alert">
            Could not send your answer. Check the connection and try again.
          </p>
        ) : null}
      </form>
    </section>
  )
}
