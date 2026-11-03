import type { JSX } from 'react'
import type { RunView } from './types'

export function RunSummary({ run, companionStopped }: { run: RunView; companionStopped: boolean }): JSX.Element {
  return (
    <div className="run-stub" data-stub="summary" data-outcome={run.ended?.outcome} data-companion-stopped={companionStopped ? 'true' : undefined}>
      {run.tasks.map((task) => task.id).join(' ')}
    </div>
  )
}
