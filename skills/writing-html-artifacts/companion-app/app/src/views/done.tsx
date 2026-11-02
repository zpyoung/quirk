import { Md } from '../blocks'
import type { Step } from '../types'
import { StepFrame, type ViewProps } from './common'

type DoneStep = Extract<Step, { kind: 'done' }>

export function DoneView({ step, changed }: ViewProps<DoneStep>) {
  return (
    <StepFrame step={step} changed={changed}>
      <Md source={step.message_md} className="done-message" />
    </StepFrame>
  )
}
