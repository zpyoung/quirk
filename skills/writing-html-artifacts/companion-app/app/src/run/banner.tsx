import { useState, type JSX } from 'react'
import { Button } from '@astryxdesign/core/Button'
import type { RunQuestion, RunView } from './types'

const DISMISSED_KEY = 'quirk-run-dismissed'

function readDismissed(): string[] {
  try {
    const parsed: unknown = JSON.parse(sessionStorage.getItem(DISMISSED_KEY) ?? '[]')
    return Array.isArray(parsed) ? parsed.filter((id): id is string => typeof id === 'string') : []
  } catch {
    return []
  }
}

function writeDismissed(ids: string[]): void {
  try {
    sessionStorage.setItem(DISMISSED_KEY, JSON.stringify(ids))
  } catch {
    return
  }
}

function dismissalKey(runId: string, questionId: string): string {
  return `${runId}:${questionId}`
}

function answeredText(question: RunQuestion): string | null {
  const answer = question.answer
  if (!answer) return null
  const what = answer.label ?? answer.text ?? answer.pick ?? ''
  if (answer.source === 'orca') return `Answered in orca ask: ${what}`
  if (answer.source === 'sdd') return `SDD assumed: ${what}`
  return null
}

function countText(open: number): string {
  if (open === 0) return 'No open questions'
  return open === 1 ? '1 question needs you' : `${open} questions need you`
}

/** Pinned list of what SDD is waiting on, oldest first, plus answers made outside the tab that it has not dismissed. */
export function NeedsYouBanner({ run, onShow }: { run: RunView; onShow(question: RunQuestion): void }): JSX.Element | null {
  const [dismissed, setDismissed] = useState<string[]>(readDismissed)
  const byAge = (a: RunQuestion, b: RunQuestion) => a.asked_at - b.asked_at
  const open = run.questions.filter((question) => question.state === 'open').sort(byAge)
  const elsewhere = run.questions
    .filter((question) => question.state === 'answered' && answeredText(question) !== null && !dismissed.includes(dismissalKey(run.run_id, question.id)))
    .sort(byAge)
  if (open.length === 0 && elsewhere.length === 0) return null

  const dismiss = (id: string) => {
    const next = [...dismissed, dismissalKey(run.run_id, id)]
    setDismissed(next)
    writeDismissed(next)
  }

  return (
    <section className="run-banner" role="region" aria-label="Needs you" data-run-part="banner">
      <p className="run-banner-count" aria-live="polite">
        {countText(open.length)}
      </p>
      <ul className="run-banner-list">
        {open.map((question) => (
          <li key={question.id} className="run-banner-item" data-kind="open">
            <span className="run-banner-text">{question.task ? `${question.task}: ${question.prompt}` : question.prompt}</span>
            <Button type="button" variant="secondary" size="sm" label="Show on graph" onClick={() => onShow(question)} />
          </li>
        ))}
        {elsewhere.map((question) => (
          <li key={question.id} className="run-banner-item" data-kind="answered">
            <span className="run-banner-text">{answeredText(question)}</span>
            <Button type="button" variant="secondary" size="sm" label="Dismiss" onClick={() => dismiss(question.id)} />
          </li>
        ))}
      </ul>
    </section>
  )
}
