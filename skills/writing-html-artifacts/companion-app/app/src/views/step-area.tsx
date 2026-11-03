import { KitProvider } from '../blocks'
import type { Actions, Draft, Snapshot, Step } from '../types'
import { ApproachesView } from './approaches'
import type { ViewProps } from './common'
import { DesignView } from './design'
import { DoneView } from './done'
import { EditCardView } from './edit-card'
import { HandOffView } from './hand-off'
import { QuestionsView } from './questions'
import { SpecReviewView } from './spec'
import { WaitingView } from './waiting'

/** Every agent HTML field of a step, so the kit libraries it needs load before any of it mounts. */
export function stepHtml(step: Step): string[] {
  const parts: string[] = [step.intro_html ?? '']
  switch (step.kind) {
    case 'questions':
      for (const q of step.questions) {
        parts.push(q.content_html ?? '')
        for (const o of q.options ?? []) parts.push(o.preview_html ?? '')
      }
      break
    case 'approaches':
      for (const a of step.approaches) parts.push(a.content_html ?? '')
      break
    case 'design-section':
      for (const s of step.sections) parts.push(s.body_html ?? '')
      break
    default:
      break
  }
  return parts
}

function renderStep(step: Step, props: Omit<ViewProps, 'step'>) {
  switch (step.kind) {
    case 'questions':
      return <QuestionsView key={step.id} step={step} {...props} />
    case 'approaches':
      return <ApproachesView key={step.id} step={step} {...props} />
    case 'design-section':
      return <DesignView key={step.id} step={step} {...props} />
    case 'spec-review':
      return <SpecReviewView key={step.id} step={step} {...props} />
    case 'edit-card':
      return <EditCardView key={step.id} step={step} {...props} />
    case 'hand-off':
      return <HandOffView key={step.id} step={step} {...props} />
    case 'done':
      return <DoneView key={step.id} step={step} {...props} />
  }
}

export interface StepAreaProps {
  snapshot: Snapshot
  token: string
  actions: Actions
  /** Step id the user has just submitted; the view shows waiting for it before the server confirms. */
  submittedStepId?: string | null
}

/** The main area: the waiting view when the step is null or submitted, otherwise the view for the step's kind. */
export function StepArea({ snapshot, token, actions, submittedStepId }: StepAreaProps) {
  const { step } = snapshot
  const waiting = !step || snapshot.step_state === 'submitted' || submittedStepId === step.id
  if (!step || waiting) return <WaitingView status={snapshot.status} actions={actions} />
  const draft: Draft | null | undefined = snapshot.draft
  const changed = new Set(step.changed?.blocks ?? [])
  return (
    <KitProvider htmlParts={stepHtml(step)}>{renderStep(step, { changed, draft, actions, token })}</KitProvider>
  )
}
