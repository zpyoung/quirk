import { useEffect, useMemo, useState, type ReactNode } from 'react'
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
import type { RunQuestion, RunView } from './types'

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
  const lostConnection = paused && !run.ended
  const hasTasks = run.tasks.length > 0

  useReadySignal(newestOpenQuestionId(run))

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
    <div className="run-view" data-stale={stale ? 'true' : undefined}>
      <header className="run-header">
        <div className="run-header-main">
          <span className="brand">Quirk run</span>
          <span className="run-branch">{run.branch}</span>
          {counts ? <span className="run-counts">{counts}</span> : null}
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
                <button type="button" aria-pressed={mode === 'graph'} onClick={() => setMode('graph')}>
                  Graph
                </button>
                <button type="button" aria-pressed={mode === 'timeline'} onClick={() => setMode('timeline')}>
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
