import { useEffect, useState } from 'react'
import { Button } from '@astryxdesign/core/Button'
import { formatElapsed, formatProgress, startedAtMs } from '../format'
import type { Actions, Status } from '../types'

function useNow(): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [])
  return now
}

export function WaitingView({ status, actions }: { status: Status | null; actions: Actions }) {
  const now = useNow()
  const started = status ? startedAtMs(status.started_at) : null
  const progress = status ? formatProgress(status.progress) : null
  const [sent, setSent] = useState(false)

  return (
    <section className="waiting" aria-labelledby="waiting-title">
      <h1 id="waiting-title" className="step-title">
        Working on it
      </h1>
      <p className="status-line" role="status" aria-live="polite">
        {status?.text ?? 'Waiting for the agent'}
      </p>
      <p className="status-meta">
        {progress ? <span className="status-progress">{progress}</span> : null}
        {started !== null ? <span className="status-elapsed">{formatElapsed(now - started)}</span> : null}
      </p>
      {status?.interruptible ? (
        <div className="actions">
          <Button
            type="button"
            variant="secondary"
            label="Continue without the rest"
            isDisabled={sent}
            onClick={() => {
              setSent(true)
              void actions.send('continue', {}).then((result) => {
                if (result === 'error') setSent(false)
              })
            }}
          />
        </div>
      ) : null}
    </section>
  )
}
