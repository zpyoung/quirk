import type { JSX } from 'react'
import { RoundCard } from './reviews'
import type { RunView } from './types'

/** Standalone page for one review round, opened from a round card's Findings link. */
export function FindingsPage({ run, round }: { run: RunView | null; round: string }): JSX.Element {
  const found = run?.rounds.find((candidate) => candidate.id === round)
  return (
    <main id="main" className="run-findings-page" data-run-part="findings-page" tabIndex={-1}>
      {!run ? (
        <p role="status">Connecting to the companion</p>
      ) : !found ? (
        <p>{`No review round ${round}.`}</p>
      ) : (
        <RoundCard round={found} full />
      )}
    </main>
  )
}
