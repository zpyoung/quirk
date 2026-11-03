import type { JSX } from 'react'
import type { RunView } from './types'

export function Reviews({ run }: { run: RunView }): JSX.Element {
  return (
    <div className="run-stub" data-stub="reviews">
      {run.rounds.map((round) => round.id).join(' ')}
    </div>
  )
}
