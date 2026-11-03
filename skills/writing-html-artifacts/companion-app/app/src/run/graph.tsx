import type { JSX, ReactNode } from 'react'
import type { RunView } from './types'

export interface RunGraphProps {
  run: RunView
  serverNow: number
  selected: string | null
  focus: { task: string; nonce: number } | null
  cardTask: string | null
  card: ReactNode
  stale: boolean
  onSelect(task: string): void
}

export function RunGraph({ run, selected, focus, cardTask, card, stale, onSelect }: RunGraphProps): JSX.Element {
  return (
    <div
      className="run-stub"
      data-stub="graph"
      data-selected={selected ?? undefined}
      data-focus={focus?.task}
      data-stale={stale ? 'true' : undefined}
    >
      {run.tasks.map((task) => (
        <button key={task.id} type="button" onClick={() => onSelect(task.id)}>
          {task.id}
        </button>
      ))}
      {cardTask ? card : null}
    </div>
  )
}
