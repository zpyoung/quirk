import { useMemo, useState, type ReactNode } from 'react'
import { Button } from '@astryxdesign/core/Button'
import type { Draft } from '../types'
import { CommentField, FormError, useDraftSync, type ViewProps } from './common'

export interface Verdict {
  value: string
  label: string
  primary?: boolean
  requiresComment?: boolean
}

/** Verdict buttons plus one comment; each button submits `{verdict, comment?}` and a "change" verdict needs a comment. */
export function VerdictBar({ verdicts, draft, actions }: { verdicts: Verdict[] } & Pick<ViewProps, 'draft' | 'actions'>): ReactNode {
  const [comment, setComment] = useState(typeof draft?.comment === 'string' ? draft.comment : '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  useDraftSync(useMemo<Draft>(() => ({ answers: {}, comment }), [comment]), actions)

  const choose = async (verdict: Verdict) => {
    if (verdict.requiresComment && !comment.trim()) {
      setError('Say what should change in the comment.')
      return
    }
    setError(null)
    setBusy(true)
    const payload: Record<string, unknown> = { verdict: verdict.value }
    if (comment.trim()) payload.comment = comment
    if ((await actions.submit(payload)) === 'error') {
      setBusy(false)
      setError('Could not send your answer. Check the connection and try again.')
    }
  }

  return (
    <div className="verdict-bar">
      <CommentField value={comment} onChange={setComment} />
      <FormError message={error} />
      <div className="actions">
        {verdicts.map((verdict) => (
          <Button
            key={verdict.value}
            type="button"
            variant={verdict.primary ? 'primary' : 'secondary'}
            label={verdict.label}
            isDisabled={busy}
            onClick={() => void choose(verdict)}
          />
        ))}
      </div>
    </div>
  )
}
