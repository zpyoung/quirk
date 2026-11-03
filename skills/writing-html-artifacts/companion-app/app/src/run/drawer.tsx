import type { JSX } from 'react'
import type { Boot } from '../types'
import type { RunTask, RunView } from './types'

export function TaskDrawer({ task, onClose }: { run: RunView; task: RunTask; boot: Boot; serverNow: number; onClose(): void }): JSX.Element {
  return (
    <div className="run-stub" data-stub="drawer" data-task={task.id}>
      <button type="button" onClick={onClose}>
        Close
      </button>
    </div>
  )
}
