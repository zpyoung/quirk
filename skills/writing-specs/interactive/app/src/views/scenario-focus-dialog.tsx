import { useEffect, useState } from 'react'
import { Button } from '@astryxdesign/core/Button'
import { Dialog, DialogHeader } from '@astryxdesign/core/Dialog'
import { HStack, VStack } from '@astryxdesign/core/Layout'
import { Text } from '@astryxdesign/core/Text'
import type { Scenario } from '../spec-types'
import { isScenarioUndecided } from '../review-state'
import { Clause, CommentField, DecisionCell, FlagToggle, OutcomeCell, type Decision } from './scenarios-view'
import { ClaudeField, Field } from './shared'
import type { ViewProps } from './view-props'

function undecidedQueue(props: ViewProps, behaviorId?: string): string[] {
  const { spec, state } = props
  const behaviors = behaviorId ? spec.behaviors.filter((b) => b.id === behaviorId) : spec.behaviors
  return behaviors.flatMap((behavior) =>
    spec.scenarios.filter((s) => s.behavior === behavior.id && isScenarioUndecided(state, s.id)).map((s) => s.id),
  )
}

function isTyping(target: EventTarget | null): boolean {
  return target instanceof HTMLElement && (target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName))
}

function FocusedScenario({ s, props, onDecided }: { s: Scenario; props: ViewProps; onDecided: (decision: Decision) => void }) {
  return (
    <VStack gap={3}>
      <Clause keyword="Given" text={s.given} />
      <Clause keyword="When" text={s.when} />
      <Field label="Then">
        <OutcomeCell s={s} props={props} />
      </Field>
      <ClaudeField label="Why">{s.explanation}</ClaudeField>
      <Field label="Your decision">
        <DecisionCell s={s} props={props} onDecided={onDecided} />
      </Field>
      <CommentField key={s.id} s={s} props={props} isInitiallyOpen />
    </VStack>
  )
}

/** Walks the scenarios that were undecided when it opened, one at a time; the list is fixed so a scenario stays put while its reason is typed. */
export function ScenarioFocusDialog({ isOpen, onClose, behaviorId, props }: { isOpen: boolean; onClose: () => void; behaviorId?: string; props: ViewProps }) {
  if (!isOpen) return null
  return <OpenFocusDialog onClose={onClose} behaviorId={behaviorId} props={props} />
}

function OpenFocusDialog({ onClose, behaviorId, props }: { onClose: () => void; behaviorId?: string; props: ViewProps }) {
  const { spec } = props
  const [queue] = useState(() => undecidedQueue(props, behaviorId))
  const [index, setIndex] = useState(0)
  const isDone = index >= queue.length
  const scenario = isDone ? undefined : spec.scenarios.find((s) => s.id === queue[index])
  const behavior = scenario ? spec.behaviors.find((b) => b.id === scenario.behavior) : undefined
  const previous = () => setIndex((i) => Math.max(0, i - 1))
  const next = () => setIndex((i) => Math.min(queue.length, i + 1))

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (isTyping(event.target) || event.metaKey || event.ctrlKey || event.altKey) return
      if (event.key === 'ArrowLeft') previous()
      else if (event.key === 'ArrowRight') next()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  const title = scenario ? `${scenario.id} · ${behavior?.rule ?? scenario.behavior}` : 'Undecided scenarios'
  const subtitle = isDone ? 'End of the list' : `Scenario ${index + 1} of ${queue.length}`
  return (
    <Dialog isOpen onOpenChange={(open) => !open && onClose()} width={760}>
      <DialogHeader
        title={title}
        subtitle={subtitle}
        startContent={scenario ? <FlagToggle key={scenario.id} s={scenario} props={props} /> : undefined}
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
          <Text>That's every undecided scenario. Anything you skipped is still undecided in the table.</Text>
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
