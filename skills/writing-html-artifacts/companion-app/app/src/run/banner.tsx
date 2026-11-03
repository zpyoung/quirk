import type { JSX } from 'react'
import type { RunQuestion, RunView } from './types'

export function NeedsYouBanner({ run, onShow }: { run: RunView; onShow(question: RunQuestion): void }): JSX.Element | null {
  const open = run.questions.filter((question) => question.state === 'open').sort((a, b) => a.asked_at - b.asked_at)
  if (open.length === 0) return null
  return (
    <div className="run-stub" data-stub="banner">
      {open.map((question) => (
        <button key={question.id} type="button" onClick={() => onShow(question)}>
          {question.id}
        </button>
      ))}
    </div>
  )
}
