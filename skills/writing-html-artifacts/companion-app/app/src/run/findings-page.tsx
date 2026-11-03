import type { JSX } from 'react'
import type { RunView } from './types'

export function FindingsPage({ run, round }: { run: RunView | null; round: string }): JSX.Element {
  return (
    <div className="run-stub" data-stub="findings-page" data-round={round} data-has-run={run ? 'true' : 'false'}>
      {round}
    </div>
  )
}
