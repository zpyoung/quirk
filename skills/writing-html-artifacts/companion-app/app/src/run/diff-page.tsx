import type { JSX } from 'react'

export function DiffPage({ task }: { task: string }): JSX.Element {
  return (
    <div className="run-stub" data-stub="diff-page" data-task={task}>
      {task}
    </div>
  )
}
