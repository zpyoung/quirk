import type { Decision } from './types'
import { statusText } from './rail'

/** Collapsible list of every locked decision; shown on every step, including the waiting one. */
export function DecisionsPanel({ decisions }: { decisions: Decision[] }) {
  return (
    <details className="panel decisions" open>
      <summary>
        Decisions <span className="count">({decisions.length})</span>
      </summary>
      {decisions.length ? (
        <ul className="decision-list">
          {decisions.map((decision) => {
            const status = statusText(decision.status)
            return (
              <li key={decision.id} className="decision" data-status={decision.status}>
                <p className="decision-label">{decision.label}</p>
                <p className="decision-value">{decision.value}</p>
                {status ? <p className="decision-status">{status}</p> : null}
                {decision.note ? <p className="muted">{decision.note}</p> : null}
              </li>
            )
          })}
        </ul>
      ) : (
        <p className="muted">Nothing is locked yet.</p>
      )}
    </details>
  )
}
