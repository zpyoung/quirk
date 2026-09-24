import type { LogicSpec, LogicSpecPayload, ReviewState } from '../spec-types'
import type { Update } from '../review-state'

/** What every review tab receives: the rendered payload, the reviewer's state, a way to edit it, and which items changed since the reviewer last saw them. */
export type ViewProps = {
  payload: LogicSpecPayload
  spec: LogicSpec
  state: ReviewState
  update: Update
  changedIds: Set<string>
  onOpenRequirement: (id: string | null) => void
}
