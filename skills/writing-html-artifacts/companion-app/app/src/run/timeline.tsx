import type { JSX } from 'react'
import type { RunView } from './types'

export function Timeline({ run }: { run: RunView; serverNow: number }): JSX.Element {
  return (
    <div className="run-stub" data-stub="timeline">
      {run.tasks.filter((task) => task.started_at !== undefined).map((task) => task.id).join(' ')}
    </div>
  )
}
