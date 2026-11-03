import type { JSX } from 'react'
import type { RunRound, RunView } from './types'

/** One round's card: title, tallies, each finding's ruling and the outcome; `full` adds each finding's lens and severity. */
export function RoundCard({ round, full = false }: { round: RunRound; full?: boolean }): JSX.Element {
  const accepted = round.findings.filter((finding) => finding.ruling === 'accepted').length
  return (
    <article className="run-round" data-round={round.id} data-full={full ? 'true' : undefined}>
      <h3 className="run-round-title">{round.title}</h3>
      <p className="run-round-summary">{`${round.findings.length} findings · ${accepted} accepted`}</p>
      <ul className="run-round-findings">
        {round.findings.map((finding) => (
          <li key={finding.id} className="run-finding" data-ruling={finding.ruling}>
            <span>
              {finding.ruling === 'accepted'
                ? `✓ ${finding.id} ${finding.reason}`
                : `✗ ${finding.id} dismissed: ${finding.reason}`}
            </span>
            {finding.fix_task ? <span className="run-tag">{`fix ${finding.fix_task} · ${round.id}`}</span> : null}
            {full ? <span className="run-finding-meta">{finding.lens}</span> : null}
            {full ? <span className="run-finding-meta" data-severity={finding.severity}>{finding.severity}</span> : null}
          </li>
        ))}
      </ul>
      <p className="run-round-outcome">{`Outcome: ${round.outcome ?? 'in progress'}`}</p>
      {full ? null : (
        <a className="run-round-link" href={`/?view=findings&round=${encodeURIComponent(round.id)}`} target="_blank" rel="noreferrer">
          Findings
        </a>
      )}
    </article>
  )
}

export function Reviews({ run }: { run: RunView }): JSX.Element {
  return (
    <div className="run-rounds" data-run-part="reviews">
      {run.rounds.map((round) => (
        <RoundCard key={round.id} round={round} />
      ))}
    </div>
  )
}
