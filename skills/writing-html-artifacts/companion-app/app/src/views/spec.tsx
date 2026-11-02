import { Md } from '../blocks'
import type { Step } from '../types'
import { StepFrame, blockAttrs, type ViewProps } from './common'
import { VerdictBar } from './verdict'

type SpecStep = Extract<Step, { kind: 'spec-review' }>

export function SpecReviewView({ step, changed, draft, actions, token }: ViewProps<SpecStep>) {
  if (step.format === 'interactive') {
    return (
      <StepFrame step={step} changed={changed}>
        <iframe className="review-frame" title="Interactive spec review" src={`/_quirk/review?t=${encodeURIComponent(token)}`} />
      </StepFrame>
    )
  }
  return (
    <StepFrame step={step} changed={changed}>
      <p className="spec-path">{step.spec_path}</p>
      {step.sections.map((section) => (
        <section key={section.id} className="spec-section" {...blockAttrs(`spec:${section.id}`, changed)}>
          <h2 className="section-title">{section.title}</h2>
          <Md source={section.body_md} />
        </section>
      ))}
      <VerdictBar
        draft={draft}
        actions={actions}
        verdicts={[
          { value: 'sign-off', label: 'Sign off', primary: true },
          { value: 'changes', label: 'Request changes', requiresComment: true },
        ]}
      />
    </StepFrame>
  )
}
