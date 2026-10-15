import { useEffect, useState } from 'react'
import { Button } from '@astryxdesign/core/Button'
import { Dialog, DialogHeader } from '@astryxdesign/core/Dialog'
import { HStack, VStack } from '@astryxdesign/core/Layout'
import { Text } from '@astryxdesign/core/Text'
import type { Scenario } from '../spec-types'
import { isScenarioUndecided, scenarioThen } from '../review-state'
import { Clause, CommentField, DecisionCell, FlagToggle, OutcomeCell, Stage2Decision, type Decision } from './scenarios-view'
import { ScenarioExampleView } from './scenario-example'
import { ClaudeField, Field } from './shared'
import type { ViewProps } from './view-props'

/** Every scenario under the behavior that owns `startScenarioId`, in spec order, whatever its decision or stage. */
function browseQueue(props: ViewProps, startScenarioId: string): string[] {
  const { spec } = props
  const behavior = spec.scenarios.find((s) => s.id === startScenarioId)?.behavior
  return spec.scenarios.filter((s) => s.behavior === behavior).map((s) => s.id)
}

function undecidedQueue(props: ViewProps, behaviorId?: string): string[] {
  const { spec, state } = props
  const behaviors = behaviorId ? spec.behaviors.filter((b) => b.id === behaviorId) : spec.behaviors
  return behaviors.flatMap((behavior) =>
    spec.scenarios.filter((s) => s.behavior === behavior.id && isScenarioUndecided(state, s.id)).map((s) => s.id),
  )
}

const ARROW_KEY_WIDGETS = '[role="radiogroup"], [role="tablist"], [role="listbox"], [role="menu"], [role="slider"]'

/** True when the key belongs to the focused control: text entry, or a widget that uses arrows for its own navigation. */
function ownsArrowKeys(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  return target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName) || target.closest(ARROW_KEY_WIDGETS) !== null
}

function FocusedScenario({ s, props, onDecided }: { s: Scenario; props: ViewProps; onDecided: (decision: Decision) => void }) {
  const isStage2 = props.spec.stage === 2
  return (
    <VStack gap={3}>
      <Clause keyword="Given" text={s.given} />
      <Clause keyword="When" text={s.when} />
      {isStage2 ? (
        <Clause keyword="Then" text={scenarioThen(props.state, s)} />
      ) : (
        <Field label="Then">
          <OutcomeCell s={s} props={props} />
        </Field>
      )}
      {s.example ? <ScenarioExampleView example={s.example} /> : null}
      <ClaudeField label="Why">{s.explanation}</ClaudeField>
      <Field label="Your decision">
        {isStage2 ? <Stage2Decision s={s} props={props} /> : <DecisionCell s={s} props={props} onDecided={onDecided} />}
      </Field>
      {isStage2 ? null : <CommentField key={s.id} s={s} props={props} isInitiallyOpen />}
    </VStack>
  )
}

type FocusDialogProps = { onClose: () => void; behaviorId?: string; startScenarioId?: string; props: ViewProps }

/**
 * Walks scenarios one at a time from a list fixed when it opens, so a scenario stays put while its reason is typed.
 * Without `startScenarioId` the list is the scenarios undecided at that moment; with it, every scenario under that
 * scenario's behavior, opened at that scenario.
 */
export function ScenarioFocusDialog({ isOpen, ...rest }: FocusDialogProps & { isOpen: boolean }) {
  if (!isOpen) return null
  return <OpenFocusDialog {...rest} />
}

function OpenFocusDialog({ onClose, behaviorId, startScenarioId, props }: FocusDialogProps) {
  const { spec } = props
  const isBrowsing = startScenarioId !== undefined
  const [queue] = useState(() => (startScenarioId ? browseQueue(props, startScenarioId) : undecidedQueue(props, behaviorId)))
  const [index, setIndex] = useState(() => (startScenarioId ? Math.max(0, queue.indexOf(startScenarioId)) : 0))
  const isDone = index >= queue.length
  const scenario = isDone ? undefined : spec.scenarios.find((s) => s.id === queue[index])
  const behavior = scenario ? spec.behaviors.find((b) => b.id === scenario.behavior) : undefined
  const previous = () => setIndex((i) => Math.max(0, i - 1))
  const next = () => setIndex((i) => Math.min(queue.length, i + 1))

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.defaultPrevented || ownsArrowKeys(event.target) || event.metaKey || event.ctrlKey || event.altKey) return
      if (event.key === 'ArrowLeft') previous()
      else if (event.key === 'ArrowRight') next()
      else return
      event.preventDefault()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  const hasExample = queue.some((id) => spec.scenarios.find((s) => s.id === id)?.example)
  const title = scenario ? `${scenario.id} · ${behavior?.rule ?? scenario.behavior}` : isBrowsing ? 'Scenarios' : 'Undecided scenarios'
  const subtitle = isDone ? 'End of the list' : `Scenario ${index + 1} of ${queue.length}`
  return (
    <Dialog isOpen onOpenChange={(open) => !open && onClose()} width={hasExample ? 1040 : 760}>
      <DialogHeader
        title={title}
        subtitle={subtitle}
        startContent={scenario && !props.readOnly ? <FlagToggle key={scenario.id} s={scenario} props={props} /> : undefined}
        onOpenChange={(open) => !open && onClose()}
      />
      <VStack gap={4} padding={4}>
        {scenario ? (
          <FocusedScenario
            key={scenario.id}
            s={scenario}
            props={props}
            onDecided={(decision) => {
              if (decision === 'approve') next()
            }}
          />
        ) : (
          <Text>
            {isBrowsing ? "That's every scenario under this behavior." : "That's every undecided scenario. Anything you skipped is still undecided in the table."}
          </Text>
        )}
        <HStack gap={2} justify="between" align="center">
          <Text type="supporting">← → to move between scenarios</Text>
          <HStack gap={2}>
            <Button variant="secondary" label="Previous" isDisabled={index === 0} onClick={previous} />
            {isDone ? <Button variant="primary" label="Done" onClick={onClose} /> : <Button variant="primary" label="Next" onClick={next} />}
          </HStack>
        </HStack>
      </VStack>
    </Dialog>
  )
}
