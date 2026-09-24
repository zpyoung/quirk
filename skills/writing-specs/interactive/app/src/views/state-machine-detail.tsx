import { Button } from '@astryxdesign/core/Button'
import { Dialog, DialogHeader } from '@astryxdesign/core/Dialog'
import { Divider } from '@astryxdesign/core/Divider'
import { Heading } from '@astryxdesign/core/Heading'
import { HStack, VStack } from '@astryxdesign/core/Layout'
import { MetadataList, MetadataListItem } from '@astryxdesign/core/MetadataList'
import { Text } from '@astryxdesign/core/Text'
import { Token } from '@astryxdesign/core/Token'
import { CHOICE_LABEL, effectivePlacement } from '../review-state'
import type { BlindSpot, LogicSpec, StateMachine, StateMachineTransition } from '../spec-types'
import { BlindSpotDetail } from './risks-view'
import { builtColor, builtLabel, nodeLabels, transitionForBlindSpot, type StateMachineSelection } from './state-machine-model'
import { ChangedToken, ClaudeField, ClaudeWroteToken, itemLabel } from './shared'
import type { ViewProps } from './view-props'

type Props = {
  machine: StateMachine
  selection: StateMachineSelection | null
  viewProps: ViewProps
  onSelect: (selection: StateMachineSelection | null) => void
}

function RequirementRows({ ids, viewProps }: { ids: string[]; viewProps: ViewProps }) {
  return (
    <VStack gap={2}>
      {ids.map((id) => {
        const requirement = viewProps.spec.requirements.find((item) => item.id === id)
        if (!requirement) return null
        const placement = effectivePlacement(viewProps.state, requirement)
        return (
          <HStack key={id} gap={2} align="center" wrap="wrap">
            <Text>{`${id} · ${requirement.summary}`}</Text>
            <ClaudeWroteToken />
            {placement ? <Token size="sm" color={placement === 'out' ? 'gray' : 'green'} label={CHOICE_LABEL[placement]} /> : null}
          </HStack>
        )
      })}
    </VStack>
  )
}

function TransitionDetail({ transition, machine, viewProps, onSelect }: { transition: StateMachineTransition; machine: StateMachine; viewProps: ViewProps; onSelect: (selection: StateMachineSelection | null) => void }) {
  const labels = nodeLabels(machine)
  const { spec, state } = viewProps
  const blindSpot: BlindSpot | undefined = transition.blindSpot ? spec.blindSpots.find((spot) => spot.id === transition.blindSpot) : undefined
  return (
    <VStack gap={4}>
      <MetadataList columns="multi">
        <MetadataListItem label="From">{labels.get(transition.from) ?? transition.from}</MetadataListItem>
        <MetadataListItem label="To">{labels.get(transition.to) ?? transition.to}</MetadataListItem>
        <MetadataListItem label="Built?">
          <Token size="sm" color={builtColor(spec, state, transition)} label={builtLabel(spec, state, transition)} />
        </MetadataListItem>
      </MetadataList>
      <ClaudeField label="What happens">{transition.event}</ClaudeField>
      {transition.reqs.length > 0 ? (
        <VStack gap={2}>
          <Heading level={3}>Requirements behind this rule</Heading>
          <RequirementRows ids={transition.reqs} viewProps={viewProps} />
        </VStack>
      ) : (
        <Text type="supporting">The behavior already exists; no requirement changes it.</Text>
      )}
      {blindSpot ? (
        <VStack gap={2}>
          <Divider />
          <Heading level={3}>Blind spot on this rule</Heading>
          <HStack gap={2} align="center" wrap="wrap">
            <Token size="sm" color="red" label={blindSpot.id} />
            <Text>{blindSpot.title}</Text>
            <Button size="sm" variant="secondary" label={`Open ${blindSpot.id}`} onClick={() => onSelect({ kind: 'blind-spot', id: blindSpot.id })} />
          </HStack>
        </VStack>
      ) : null}
    </VStack>
  )
}

function CausedBySources({ ids, spec }: { ids: string[]; spec: LogicSpec }) {
  return (
    <VStack gap={2}>
      {ids.map((id) => <Text key={id}>{`${id} · ${itemLabel(spec, id)}`}</Text>)}
    </VStack>
  )
}

function BlindSpotDetailSection({ spot, machine, viewProps, onSelect }: { spot: BlindSpot; machine: StateMachine; viewProps: ViewProps; onSelect: (selection: StateMachineSelection | null) => void }) {
  const onTransition = transitionForBlindSpot(machine, spot.id)
  return (
    <VStack gap={4}>
      <BlindSpotDetail spot={spot} props={viewProps} />
      <Divider />
      <VStack gap={2}>
        <Heading level={3}>Caused by</Heading>
        <CausedBySources ids={spot.sources} spec={viewProps.spec} />
      </VStack>
      {onTransition ? (
        <HStack gap={2} align="center" wrap="wrap">
          <Text type="supporting">{`Sits on: ${onTransition.short}.`}</Text>
          <Button size="sm" variant="secondary" label="Open that transition" onClick={() => onSelect({ kind: 'transition', id: onTransition.id })} />
        </HStack>
      ) : null}
    </VStack>
  )
}

/** The detail pop-up for whatever the reviewer clicked on the state machine diagram: a transition, or a blind spot with its acceptance fields. */
export function StateMachineDetailDialog({ machine, selection, viewProps, onSelect }: Props) {
  if (!selection) return null
  const close = () => onSelect(null)
  const transition = selection.kind === 'transition' ? machine.transitions.find((item) => item.id === selection.id) : undefined
  const blindSpot = selection.kind === 'blind-spot' ? viewProps.spec.blindSpots.find((item) => item.id === selection.id) : undefined
  if (!transition && !blindSpot) return null
  const labels = nodeLabels(machine)
  return (
    <Dialog isOpen onOpenChange={(open) => !open && close()} width={720} maxHeight="90dvh" purpose="form">
      <DialogHeader
        title={transition ? `${labels.get(transition.from) ?? transition.from} → ${labels.get(transition.to) ?? transition.to}` : `Blind spot ${blindSpot!.id}`}
        subtitle={transition ? 'Transition' : undefined}
        onOpenChange={(open) => !open && close()}
      />
      <VStack gap={4} padding={4}>
        {blindSpot ? <ChangedToken id={blindSpot.id} changedIds={viewProps.changedIds} /> : null}
        {transition ? (
          <TransitionDetail transition={transition} machine={machine} viewProps={viewProps} onSelect={onSelect} />
        ) : (
          <BlindSpotDetailSection spot={blindSpot!} machine={machine} viewProps={viewProps} onSelect={onSelect} />
        )}
      </VStack>
    </Dialog>
  )
}
