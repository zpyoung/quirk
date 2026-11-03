import type { JSX } from 'react'
import { formatElapsed, taskElapsedMs } from './format'
import type { RunView } from './types'

const HEADINGS = { clean: 'Run finished', blocked: 'Run blocked', stopped: 'Run stopped' } as const
const NEXT_STEPS = { merge: 'Next: merge', pr: 'Next: open a PR', keep: 'Next: keep the branch' } as const

/** Final state of an ended run; task times are frozen at the run's end. */
export function RunSummary({ run, companionStopped }: { run: RunView; companionStopped: boolean }): JSX.Element {
  const ended = run.ended
  const endMs = ended ? ended.at * 1000 : run.now * 1000
  return (
    <main id="main" className="run-main run-summary" data-run-part="summary" tabIndex={-1} data-outcome={ended?.outcome}>
      <h2>{ended ? HEADINGS[ended.outcome] : 'Run finished'}</h2>
      {companionStopped ? <p className="run-summary-note">The companion has stopped; this is the final state.</p> : null}
      <p className="run-summary-branch">{run.branch}</p>
      {ended?.next_step ? <p className="run-summary-next">{NEXT_STEPS[ended.next_step]}</p> : null}
      <table className="run-summary-tasks">
        <thead>
          <tr>
            <th scope="col">Task</th>
            <th scope="col">Status</th>
            <th scope="col">Time</th>
          </tr>
        </thead>
        <tbody>
          {run.tasks.map((task) => {
            const elapsed = taskElapsedMs(task, endMs)
            return (
              <tr key={task.id} data-status={task.status}>
                <th scope="row">{task.id}</th>
                <td>{task.status}</td>
                <td>{elapsed === null ? '—' : formatElapsed(elapsed)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
      {run.rounds.length > 0 ? (
        <ul className="run-summary-rounds">
          {run.rounds.map((round) => (
            <li key={round.id}>{`${round.title}: ${round.outcome ?? 'in progress'}`}</li>
          ))}
        </ul>
      ) : null}
    </main>
  )
}
