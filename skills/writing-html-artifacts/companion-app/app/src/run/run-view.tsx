import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useReadySignal } from '../notify'
import type { Boot, Snapshot } from '../types'
import { NeedsYouBanner } from './banner'
import { TaskDrawer } from './drawer'
import { countsLine, serverOffsetMs, staleSince, staleText, useNow } from './format'
import { RunGraph } from './graph'
import { QuestionCard } from './question-card'
import { Reviews } from './reviews'
import { RunSummary } from './summary'
import { Timeline } from './timeline'
import type { RunQuestion, RunStatus, RunView } from './types'

type Mode = 'graph' | 'timeline'

export interface RunPageProps {
  snapshot: Snapshot
  boot: Boot
  paused: boolean
  headerExtras?: ReactNode
  /** Opens the card for this question on first render; lets the static checks reach the post-selection state. */
  initialCardQuestionId?: string | null
}

export interface ShowState {
  mode: Mode
  cardQuestionId: string | null
  focus: { task: string; nonce: number } | null
}

/** State after "Show on graph": always back on the graph so the card and focused node are visible. */
export function showOnGraphState(question: RunQuestion, nonce: number): ShowState {
  return { mode: 'graph', cardQuestionId: question.id, focus: question.task ? { task: question.task, nonce } : null }
}

function newestOpenQuestionId(run: RunView): string | null {
  let newest: RunQuestion | null = null
  for (const question of run.questions) {
    if (question.state === 'open' && (!newest || question.asked_at >= newest.asked_at)) newest = question
  }
  return newest?.id ?? null
}

/** Tab title: "Quirk run · <branch>", prefixed "(n) " while n questions are open. */
export function runTitle(run: RunView): string {
  const open = run.questions.filter((question) => question.state === 'open').length
  return `${open > 0 ? `(${open}) ` : ''}Quirk run · ${run.branch}`
}

/**
 * Sets the tab title and restores the previous one on unmount. A hidden tab is left alone so the ready signal's
 * "(1) Your turn" stays up; the latest title is applied when the tab is shown again.
 */
function useTabTitle(title: string): void {
  const previous = useRef<string | null>(null)
  const first = useRef(true)
  useEffect(() => {
    previous.current = document.title
    return () => {
      if (previous.current !== null) document.title = previous.current
    }
  }, [])
  useEffect(() => {
    const apply = () => {
      if (!document.hidden) document.title = title
    }
    if (first.current) {
      first.current = false
      document.title = title
    } else {
      apply()
    }
    window.addEventListener('focus', apply)
    document.addEventListener('visibilitychange', apply)
    return () => {
      window.removeEventListener('focus', apply)
      document.removeEventListener('visibilitychange', apply)
    }
  }, [title])
}

// attention first, so the chips that need a decision lead the row
const CHIP_ORDER: [RunStatus, string, boolean][] = [
  ['needs-you', 'needs you', true],
  ['failed', 'failed', true],
  ['retrying', 'retrying', false],
  ['running', 'running', false],
  ['queued', 'queued', false],
  ['stopped', 'stopped', false],
  ['skipped', 'skipped', false],
  ['missing', 'missing', false],
]

/** Header counts split for display: the passed fraction and one entry per non-zero status. */
export function headerCounts(run: RunView): { passedText: string; chips: { status: RunStatus; text: string; strong: boolean }[] } | null {
  if (run.tasks.length === 0) return null
  const tally = new Map<RunStatus, number>()
  for (const task of run.tasks) tally.set(task.status, (tally.get(task.status) ?? 0) + 1)
  const chips = CHIP_ORDER.flatMap(([status, label, strong]) => {
    const n = tally.get(status) ?? 0
    return n > 0 ? [{ status, text: `${n} ${label}`, strong }] : []
  })
  return { passedText: `${tally.get('passed') ?? 0} of ${run.tasks.length} passed`, chips }
}

/** The live run page: header, needs-you banner, graph or timeline, reviews and the selected task's drawer. */
export function RunPage({ snapshot, boot, paused, headerExtras, initialCardQuestionId }: RunPageProps) {
  const run = snapshot.run
  if (!run) return null
  return (
    <RunPageBody run={run} boot={boot} paused={paused} headerExtras={headerExtras} initialCardQuestionId={initialCardQuestionId} />
  )
}

function RunPageBody({
  run,
  boot,
  paused,
  headerExtras,
  initialCardQuestionId = null,
}: {
  run: RunView
  boot: Boot
  paused: boolean
  headerExtras?: ReactNode
  initialCardQuestionId?: string | null
}) {
  const [mode, setMode] = useState<Mode>('graph')
  const [selected, setSelected] = useState<string | null>(null)
  const [focus, setFocus] = useState<{ task: string; nonce: number } | null>(null)
  const [cardQuestionId, setCardQuestionId] = useState<string | null>(initialCardQuestionId)

  const clientNow = useNow()
  const offset = useMemo(() => serverOffsetMs(run, Date.now()), [run.now])
  const serverNow = clientNow + offset
  const staleSeconds = staleSince(run, serverNow)
  const stale = staleSeconds !== null
  const counts = countsLine(run)
  const header = headerCounts(run)
  const lostConnection = paused && !run.ended
  const hasTasks = run.tasks.length > 0

  useReadySignal(newestOpenQuestionId(run))
  useTabTitle(runTitle(run))

  const cardQuestion = cardQuestionId ? (run.questions.find((question) => question.id === cardQuestionId) ?? null) : null
  const closeCard = () => {
    setCardQuestionId(null)
    setFocus(null)
  }
  useEffect(() => {
    if (cardQuestionId && !cardQuestion) setCardQuestionId(null)
  }, [cardQuestionId, cardQuestion])

  const showOnGraph = (question: RunQuestion) => {
    const next = showOnGraphState(question, Date.now())
    setMode(next.mode)
    setCardQuestionId(next.cardQuestionId)
    setFocus(next.focus)
  }

  const selectedTask = selected ? (run.tasks.find((task) => task.id === selected) ?? null) : null
  const cardTask = cardQuestion?.task ?? null
  const card = cardQuestion ? <QuestionCard question={cardQuestion} boot={boot} onClose={closeCard} /> : null

  return (
    <div className="run-view" data-stale={stale ? 'true' : undefined} data-drawer={selectedTask && !run.ended ? 'open' : undefined}>
      <header className="run-header">
        <div className="run-header-main">
          <span className="brand">Quirk run</span>
          <span className="run-branch">{run.branch}</span>
          {header ? (
            <span className="run-counts">
              <span className="sr-only">{counts}</span>
              <span className="run-counts-passed" aria-hidden="true">
                {header.passedText}
              </span>
              <span className="run-counts-chips" aria-hidden="true">
                {header.chips.map((chip) => (
                  <span key={chip.status} className="run-chip" data-status={chip.status} data-strong={chip.strong ? 'true' : undefined}>
                    {chip.text}
                  </span>
                ))}
              </span>
            </span>
          ) : null}
          {headerExtras}
        </div>
        <div className="run-header-status" role="status" aria-live="polite">
          {run.status_text ? <p className="run-status-line">{run.status_text}</p> : null}
          {staleSeconds !== null ? <p className="run-stale">{staleText(staleSeconds)}</p> : null}
          {lostConnection ? <p className="run-lost">Lost connection to the companion</p> : null}
        </div>
      </header>
      {run.ended ? (
        <RunSummary run={run} companionStopped={paused} />
      ) : (
        <main id="main" className="run-main" tabIndex={-1}>
          <NeedsYouBanner run={run} onShow={showOnGraph} />
          {cardQuestion && (!cardQuestion.task || !hasTasks) ? <section className="run-card-panel">{card}</section> : null}
          {hasTasks ? (
            <>
              <div className="run-switch" role="group" aria-label="View">
                <button type="button" className="run-switch-seg" aria-pressed={mode === 'graph'} onClick={() => setMode('graph')}>
                  Graph
                </button>
                <button type="button" className="run-switch-seg" aria-pressed={mode === 'timeline'} onClick={() => setMode('timeline')}>
                  Timeline
                </button>
              </div>
              {mode === 'graph' ? (
                <RunGraph
                  run={run}
                  serverNow={serverNow}
                  selected={selected}
                  focus={focus}
                  cardTask={cardTask}
                  card={card}
                  stale={stale}
                  onSelect={setSelected}
                />
              ) : (
                <Timeline run={run} serverNow={serverNow} />
              )}
              {run.rounds.length > 0 ? (
                <section className="run-reviews" aria-labelledby="run-reviews-title">
                  <h2 id="run-reviews-title">Reviews</h2>
                  <Reviews run={run} />
                </section>
              ) : null}
              {selectedTask ? (
                <TaskDrawer run={run} task={selectedTask} boot={boot} serverNow={serverNow} onClose={() => setSelected(null)} />
              ) : null}
            </>
          ) : null}
        </main>
      )}
    </div>
  )
}
