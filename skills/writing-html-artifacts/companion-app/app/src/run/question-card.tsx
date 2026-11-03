import type { JSX } from 'react'
import type { Boot } from '../types'
import type { RunQuestion } from './types'

export function QuestionCard({ question, onClose }: { question: RunQuestion; boot: Boot; onClose(): void }): JSX.Element {
  return (
    <div className="run-stub" data-stub="question-card" data-question={question.id}>
      <button type="button" onClick={onClose}>
        Close
      </button>
    </div>
  )
}
