import { useEffect, useRef, useState, type JSX } from 'react'
import { Button } from '@astryxdesign/core/Button'
import { renderMarkdown } from '../markdown'
import type { Boot } from '../types'
import { openInOrca, postRunEvent } from './api'
import { ConfirmDialog, confirmTone, retryLines, stopChainLines, type ConfirmText } from './confirm'
import { formatElapsed } from './format'
import { QuestionCard } from './question-card'
import type { RunTask, RunView } from './types'

function ExternalIcon(): JSX.Element {
  return (
    <svg className="run-link-icon" viewBox="0 0 16 16" width="12" height="12" aria-hidden="true" focusable="false">
      <path d="M9 2h5v5M14 2 7.5 8.5M12 9.5V13a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h3.5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

const STOPPABLE = new Set(['queued', 'running', 'retrying', 'needs-you', 'failed'])

type Pending = { kind: 'stop' | 'retry'; text: ConfirmText }

/** Side panel for one task: its open questions to answer, status, attempts, contract, links to its diff and findings, and the Stop chain and Retry actions. */
export function TaskDrawer({
  run,
  task,
  boot,
  serverNow,
  onClose,
}: {
  run: RunView
  task: RunTask
  boot: Boot
  serverNow: number
  onClose(): void
}): JSX.Element {
  const [confirm, setConfirm] = useState<Pending | null>(null)
  const [busy, setBusy] = useState(false)
  const [problem, setProblem] = useState<string | null>(null)
  const [opening, setOpening] = useState(false)
  const [opened, setOpened] = useState<{ ok: boolean; text: string } | null>(null)
  const root = useRef<HTMLElement>(null)
  const confirming = confirm !== null

  useEffect(() => {
    setConfirm(null)
    setProblem(null)
    setOpened(null)
    root.current?.focus()
  }, [task.id])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !confirming && !event.defaultPrevented) onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [confirming, onClose])

  const submit = async () => {
    if (!confirm || busy) return
    setBusy(true)
    const result = await postRunEvent(boot, confirm.kind === 'stop' ? 'run-stop' : 'run-retry', { task: task.id })
    setBusy(false)
    setConfirm(null)
    if (result.kind === 'refused') setProblem(`SDD can't do that now: ${result.reason}`)
    else if (result.kind === 'error') setProblem('Could not send that. Check the connection and try again.')
    else setProblem(null)
  }

  const openWorktree = async () => {
    if (opening) return
    setOpening(true)
    setOpened(null)
    const result = await openInOrca(boot, run.run_id, task.id)
    setOpening(false)
    if (result.kind === 'opened') {
      setOpened({ ok: true, text: result.action === 'switched' ? 'Opened in Orca' : 'Opened a new terminal in Orca' })
    } else {
      setOpened({ ok: false, text: result.message })
    }
  }

  const openQuestions = run.questions.filter((question) => question.state === 'open' && question.task === task.id)
  const contract = renderMarkdown(task.contract_md)
  const canStop = STOPPABLE.has(task.status)
  const canRetry = task.status === 'failed'
  const canOpen = Boolean(task.worktree) && !run.ended

  return (
    <>
    <div className="run-drawer-scrim" aria-hidden="true" onClick={onClose} />
      <aside ref={root} className="run-drawer" aria-label={`Task ${task.id}`} tabIndex={-1} data-run-part="drawer" data-task={task.id}>
        <header className="run-drawer-head">
          <div>
            <h2 className="run-drawer-title">{task.title}</h2>
            <p className="run-drawer-id">{task.id}</p>
          </div>
          <Button type="button" variant="secondary" size="sm" label="Close" onClick={onClose} />
        </header>

        <p className="run-drawer-status" data-status={task.status}>
          <span className="run-drawer-status-word">{task.status}</span>
          {task.reason ? <span className="run-drawer-reason">{task.reason}</span> : null}
        </p>

        {openQuestions.map((question) => (
          <section key={question.id} className="run-drawer-question" aria-label="Needs you">
            <h3>Needs you</h3>
            <QuestionCard question={question} boot={boot} inline />
          </section>
        ))}

        {task.attempts.length > 0 ? (
          <section aria-label="Attempts">
            <h3>Attempts</h3>
            <ol className="run-drawer-attempts">
              {task.attempts.map((attempt) => (
                <li key={attempt.n}>
                  {`Attempt ${attempt.n}`}
                  <span className="run-drawer-elapsed">
                    {formatElapsed((attempt.end === undefined ? serverNow : attempt.end * 1000) - attempt.start * 1000)}
                  </span>
                  <span className="run-drawer-outcome">{attempt.outcome ?? 'running'}</span>
                </li>
              ))}
            </ol>
          </section>
        ) : null}

        {contract ? (
          <section aria-label="Contract">
            <h3>Contract</h3>
            <div className="md run-drawer-contract" dangerouslySetInnerHTML={{ __html: contract }} />
          </section>
        ) : null}

        {task.labels.length > 0 ? (
          <ul className="run-drawer-labels" aria-label="Labels">
            {task.labels.map((label) => (
              <li key={label}>{label}</li>
            ))}
          </ul>
        ) : null}
        {task.mismatch ? <p className="run-drawer-mismatch">{task.mismatch.text}</p> : null}

        <p className="run-drawer-links">
          <a className="run-link-button" href={`/?view=diff&task=${encodeURIComponent(task.id)}`} target="_blank" rel="noreferrer">
            Diff
            <ExternalIcon />
            <span className="sr-only"> (opens in a new tab)</span>
          </a>
          {task.round ? (
            <a className="run-link-button" href={`/?view=findings&round=${encodeURIComponent(task.round)}`} target="_blank" rel="noreferrer">
              Findings
              <ExternalIcon />
              <span className="sr-only"> (opens in a new tab)</span>
            </a>
          ) : null}
          {canOpen ? (
            <Button
              type="button"
              variant="secondary"
              size="sm"
              label="Open in Orca"
              isDisabled={opening}
              onClick={() => void openWorktree()}
            />
          ) : null}
        </p>
        {opened?.ok ? (
          <p className="run-drawer-opened" role="status">
            {opened.text}
          </p>
        ) : null}
        {opened && !opened.ok ? (
          <p className="run-drawer-problem" role="alert">
            {opened.text}
          </p>
        ) : null}

        {task.pending_action ? (
          <p className="run-drawer-pending" role="status">
            {task.pending_action === 'stop' ? 'Stop requested, waiting for SDD' : 'Retry requested, waiting for SDD'}
          </p>
        ) : (
          <div className="run-drawer-actions">
            {canStop ? (
              <Button
                type="button"
                variant="secondary"
                size="sm"
                label="Stop chain"
                onClick={() => setConfirm({ kind: 'stop', text: stopChainLines(run, task.id) })}
              />
            ) : null}
            {canRetry ? (
              <Button
                type="button"
                variant="primary"
                size="sm"
                label="Retry"
                onClick={() => setConfirm({ kind: 'retry', text: retryLines(task) })}
              />
            ) : null}
          </div>
        )}
        {problem ? (
          <p className="run-drawer-problem" role="alert">
            {problem}
          </p>
        ) : null}

        {confirm ? (
          <ConfirmDialog
            title={confirm.text.title}
            lines={confirm.text.lines}
            confirmLabel={confirm.kind === 'stop' ? 'Stop chain' : 'Retry'}
            tone={confirmTone(confirm.kind)}
            onConfirm={() => void submit()}
            onCancel={() => setConfirm(null)}
          />
        ) : null}
      </aside>
    </>
  )
}
