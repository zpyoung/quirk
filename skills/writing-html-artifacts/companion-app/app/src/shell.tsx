import type { ReactNode } from 'react'
import { ChatPanel } from './chat'
import { CommentsProvider, useComments } from './comments'
import { DecisionsPanel } from './decisions'
import { Recap, Rail } from './rail'
import type { Actions, Snapshot, StageId } from './types'
import { StepArea } from './views/step-area'

export interface ShellViewProps {
  snapshot: Snapshot
  token: string
  actions: Actions
  paused: boolean
  submittedStepId: string | null
  openStage: StageId | null
  onOpenStage(stage: StageId | null): void
  headerExtras?: ReactNode
}

/** The step area, wrapped so the comment layer can watch it for commentable blocks. */
function StepRoot({ children }: { children: ReactNode }) {
  const { rootRef } = useComments()
  return (
    <div ref={rootRef} className="step-root">
      {children}
    </div>
  )
}

/** The four-region layout: rail, main step area, and a right column that holds the Chat and Decisions panels. */
export function ShellView({ snapshot, token, actions, paused, submittedStepId, openStage, onOpenStage, headerExtras }: ShellViewProps) {
  return (
    <CommentsProvider threads={snapshot.threads} stepId={snapshot.step?.id ?? null} actions={actions}>
      <div className="shell">
        <header className="topbar">
          <span className="brand">Quirk brainstorm</span>
          <div className="reconnect" role="status" aria-live="polite">
            {paused ? <span className="reconnect-banner">Paused, reconnecting</span> : null}
          </div>
          {headerExtras}
        </header>
        <div className="shell-grid">
          <Rail stages={snapshot.stages} openStage={openStage} onOpen={(stage) => onOpenStage(openStage === stage ? null : stage)} />
          <main id="main" className="main" tabIndex={-1}>
            {openStage ? <Recap key={openStage} stage={openStage} decisions={snapshot.decisions} actions={actions} onClose={() => onOpenStage(null)} /> : null}
            <div hidden={openStage !== null}>
              <StepRoot>
                <StepArea snapshot={snapshot} token={token} actions={actions} submittedStepId={submittedStepId} />
              </StepRoot>
            </div>
          </main>
          <aside className="side" aria-label="Session">
            <ChatPanel chat={snapshot.chat} actions={actions} />
            <DecisionsPanel decisions={snapshot.decisions} />
          </aside>
        </div>
      </div>
    </CommentsProvider>
  )
}

export function NotConnected() {
  return (
    <div className="shell shell-offline">
      <main className="main">
        <section className="offline-card" role="status">
          <h1 className="step-title">Not connected</h1>
          <p>This page runs inside a brainstorming session. Open the link the agent printed in your terminal to continue.</p>
        </section>
      </main>
    </div>
  )
}

export function Connecting({ paused }: { paused: boolean }) {
  return (
    <div className="shell shell-offline">
      <main className="main">
        <p className="status-line" role="status" aria-live="polite">
          {paused ? 'Paused, reconnecting' : 'Connecting to the session'}
        </p>
      </main>
    </div>
  )
}
