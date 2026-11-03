import { useEffect, useRef, type JSX, type KeyboardEvent } from 'react'
import { Button } from '@astryxdesign/core/Button'
import type { RunTask, RunView } from './types'

export interface ConfirmText {
  title: string
  lines: string[]
}

/** Every task that must finish before `taskId`, through either edge kind, in the run's task order. */
function predecessorIds(run: RunView, taskId: string): Set<string> {
  const seen = new Set<string>()
  const queue = [taskId]
  while (queue.length > 0) {
    const current = queue.pop() as string
    for (const edge of run.edges) {
      if (edge.to === current && !seen.has(edge.from)) {
        seen.add(edge.from)
        queue.push(edge.from)
      }
    }
  }
  return seen
}

/** What stopping the chain from `taskId` will do, one sentence per consequence, for the confirm dialog. */
export function stopChainLines(run: RunView, taskId: string): ConfirmText {
  const task = run.tasks.find((candidate) => candidate.id === taskId)
  const lines: string[] = []
  if (task?.status === 'failed') {
    lines.push(`${taskId} stays failed; any uncommitted work in its worktree is discarded.`)
  } else if (task?.status === 'running' || task?.status === 'retrying' || task?.status === 'needs-you') {
    lines.push(`${taskId} stops now; any uncommitted work in its worktree is discarded.`)
  } else {
    lines.push(`${taskId} won't run and is marked stopped.`)
  }
  for (const id of task?.downstream ?? []) lines.push(`${id} won't run and is marked stopped.`)
  const predecessors = predecessorIds(run, taskId)
  const committed = run.tasks.filter((candidate) => predecessors.has(candidate.id) && candidate.status === 'passed').map((candidate) => candidate.id)
  if (committed.length > 0) lines.push(`${committed.join(' and ')} ${committed.length === 1 ? 'is' : 'are'} committed and stay${committed.length === 1 ? 's' : ''}.`)
  lines.push('Every other task keeps going.')
  return { title: `Stop the chain from ${taskId}?`, lines }
}

/** What retrying a failed task will do: the next attempt number and why the last one failed. */
export function retryLines(task: RunTask): ConfirmText {
  const lines = [`This starts attempt ${task.attempt + 1}.`]
  if (task.reason) lines.push(`The last attempt failed: ${task.reason}.`)
  return { title: `Retry ${task.id}?`, lines }
}

const FOCUSABLE = 'button:not([disabled]), [href], input:not([disabled]), [tabindex]:not([tabindex="-1"])'

/** Modal confirmation: focus moves in, Tab stays inside, Escape cancels and focus returns to the opener. */
export function ConfirmDialog({
  title,
  lines,
  confirmLabel,
  onConfirm,
  onCancel,
}: {
  title: string
  lines: string[]
  confirmLabel: string
  onConfirm(): void
  onCancel(): void
}): JSX.Element {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null
    ref.current?.focus()
    return () => opener?.focus()
  }, [])

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Escape') {
      event.preventDefault()
      event.stopPropagation()
      onCancel()
      return
    }
    if (event.key !== 'Tab' || !ref.current) return
    const items = Array.from(ref.current.querySelectorAll<HTMLElement>(FOCUSABLE))
    if (items.length === 0) return
    const first = items[0]
    const last = items[items.length - 1]
    if (event.shiftKey && (document.activeElement === first || document.activeElement === ref.current)) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first.focus()
    }
  }

  return (
    <div className="run-confirm-backdrop">
      <div
        ref={ref}
        className="run-confirm"
        role="dialog"
        aria-modal="true"
        aria-labelledby="run-confirm-title"
        tabIndex={-1}
        onKeyDown={onKeyDown}
      >
        <h2 id="run-confirm-title">{title}</h2>
        <ul>
          {lines.map((line, index) => (
            <li key={index}>{line}</li>
          ))}
        </ul>
        <div className="run-confirm-actions">
          <Button type="button" variant="secondary" size="sm" label="Cancel" onClick={onCancel} />
          <Button type="button" variant="primary" size="sm" label={confirmLabel} onClick={onConfirm} />
        </div>
      </div>
    </div>
  )
}
