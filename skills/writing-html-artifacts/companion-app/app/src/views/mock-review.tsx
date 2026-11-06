import type { Step } from '../types'
import { StepFrame, type ViewProps } from './common'

type MockReviewStep = Extract<Step, { kind: 'mock-review' }>

/** The mock review harness owns the verdict, so the shell renders only the frame and no verdict bar. */
export function MockReviewView({ step, changed, token }: ViewProps<MockReviewStep>) {
  return (
    <StepFrame step={step} changed={changed}>
      <iframe className="mock-frame" title="Mock review" src={`/_quirk/mock/${step.version}?t=${encodeURIComponent(token)}`} />
    </StepFrame>
  )
}
