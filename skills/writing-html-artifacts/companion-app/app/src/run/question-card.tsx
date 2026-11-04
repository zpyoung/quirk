import { useEffect, useId, useRef, useState, type FormEvent, type JSX } from 'react'
import { Button } from '@astryxdesign/core/Button'
import type { Boot } from '../types'
import { postRunEvent } from './api'
import type { RunAnswer, RunQuestion } from './types'

type Status = 'idle' | 'sending' | 'sent' | 'error'

const SENT_CLOSE_MS = 4000

function answerText(answer: RunAnswer): string {
  return answer.label ?? answer.text ?? answer.pick ?? ''
}

function sentLine(what: string): string {
  return `Sent: ${what}. SDD will act on it at its next step.`
}

function answeredLine(answer: RunAnswer | undefined): string {
  if (!answer) return 'Already answered.'
  const what = answerText(answer)
  const where = answer.source === 'orca' ? 'in orca ask' : answer.source === 'sdd' ? 'by SDD' : 'in the tab'
  return `Already answered ${where}: ${what}`
}

export interface QuestionCardProps {
  question: RunQuestion
  boot: Boot
  /** Card mode only: closes the card; also called a few seconds after a sent answer. */
  onClose?(): void
  /** Answer form without the card chrome, for hosts that already show the task (banner, drawer). */
  inline?: boolean
  /** Inline only: keep the prompt for screen readers but hide it, when the host already shows it. */
  hidePrompt?: boolean
}

/** One open question: its options as radios plus an Other box; sends exactly one of a pick or typed text. */
export function QuestionCard(props: QuestionCardProps): JSX.Element {
  return <QuestionCardBody key={props.question.id} {...props} />
}

function QuestionCardBody({ question, boot, onClose, inline = false, hidePrompt = false }: QuestionCardProps): JSX.Element {
  const groupName = useId()
  const [pick, setPick] = useState<string | null>(null)
  const [text, setText] = useState('')
  const [status, setStatus] = useState<Status>('idle')
  const [lost, setLost] = useState<RunAnswer | null>(null)
  const [sentWhat, setSentWhat] = useState<string | null>(null)
  const closeRef = useRef(onClose)
  closeRef.current = onClose

  const answer = lost ?? question.answer
  const sentText = sentWhat ?? (answer?.source === 'tab' ? answerText(answer) : null)
  const sentNote = sentText !== null
  useEffect(() => {
    if (!sentNote) return
    const timer = setTimeout(() => closeRef.current?.(), SENT_CLOSE_MS)
    return () => clearTimeout(timer)
  }, [sentNote])

  const header = inline ? null : (
    <header className="run-card-head">
      {question.task ? <span className="run-card-task">{question.task}</span> : null}
      {question.header ? <span className="run-card-header">{question.header}</span> : null}
      {onClose ? <Button type="button" variant="secondary" size="sm" label="Close" onClick={onClose} /> : null}
    </header>
  )
  // inline forms use their own marker so a card beside the node and the banner's form never share a locator
  const shell = {
    className: inline ? 'run-card run-card--inline' : 'run-card',
    'aria-label': inline ? `Answer ${question.task ?? 'question'}` : 'Question',
    'data-run-part': inline ? 'question-answer' : 'question-card',
    'data-question': question.id,
  }
  const promptClass = hidePrompt ? 'run-card-prompt sr-only' : 'run-card-prompt'

  if (question.state === 'answered' || lost || sentWhat !== null) {
    return (
      <section {...shell}>
        {header}
        {hidePrompt ? null : <p className="run-card-prompt">{question.prompt}</p>}
        <p className="run-card-note" role="status">
          {sentText !== null ? sentLine(sentText) : answeredLine(answer)}
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
    if (result.kind === 'ok' || result.kind === 'duplicate') {
      setStatus('sent')
      setSentWhat(pick !== null ? (question.options.find((option) => option.value === pick)?.label ?? pick) : typed)
    } else if (result.kind === 'answered') setLost(result.answer)
    else setStatus('error')
  }

  return (
    <section {...shell}>
      {header}
      <form onSubmit={send} className="run-card-form">
        <fieldset className="run-card-fields" disabled={locked}>
          <legend className={promptClass}>{question.prompt}</legend>
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
                  {option.value === question.recommended ? (
                    <>
                      <span className="sr-only">, recommended</span>
                      <span className="run-card-tag" aria-hidden="true">
                        Recommended
                      </span>
                    </>
                  ) : null}
                </span>
                {option.description ? (
                  <>
                    <span className="sr-only">. </span>
                    <span className="run-card-option-desc">{option.description}</span>
                  </>
                ) : null}
              </span>
            </label>
          ))}
          <label className="run-card-other">
            <span>Other</span>
            <input
              type="text"
              placeholder={inline ? 'Type another answer' : undefined}
              value={text}
              onChange={(event) => {
                setText(event.target.value)
                if (event.target.value.trim() !== '') setPick(null)
              }}
            />
          </label>
        </fieldset>
        <Button type="submit" variant="primary" size="sm" label="Send" isDisabled={!canSend} />
        {status === 'error' ? (
          <p className="run-card-note" data-tone="error" role="alert">
            Could not send your answer. Check the connection and try again.
          </p>
        ) : null}
      </form>
    </section>
  )
}
