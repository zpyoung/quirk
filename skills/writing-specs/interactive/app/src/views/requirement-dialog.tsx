import { useState } from 'react'
import { Banner } from '@astryxdesign/core/Banner'
import { Dialog, DialogHeader } from '@astryxdesign/core/Dialog'
import { Divider } from '@astryxdesign/core/Divider'
import { Heading } from '@astryxdesign/core/Heading'
import { HStack, VStack } from '@astryxdesign/core/Layout'
import { MetadataList, MetadataListItem } from '@astryxdesign/core/MetadataList'
import { RadioList, RadioListItem } from '@astryxdesign/core/RadioList'
import { Selector } from '@astryxdesign/core/Selector'
import { Text } from '@astryxdesign/core/Text'
import { TextArea } from '@astryxdesign/core/TextArea'
import type { LogicSpec, Placement, Requirement, ReviewState, ScopeCondition } from '../spec-types'
import {
  CHOICE_LABEL,
  CONDITION_LABEL,
  GROUP_LABEL,
  effectiveCondition,
  effectivePlacement,
  placementInSpec,
  requirementMoved,
  scopeWarnings,
  type Update,
} from '../review-state'
import { ChangedToken, CertaintyToken, ClaudeField, ProvenanceToken, SpecMarkdown } from './shared'
import { CONDITIONS, isAwaitingCall, setPlacement } from './board-model'
import { useScopeOutGuard } from './scope-out-guard'

type DialogProps = { requirement: Requirement | null; spec: LogicSpec; state: ReviewState; update: Update; changedIds: Set<string>; onClose: () => void }
type DetailProps = { requirement: Requirement; spec: LogicSpec; state: ReviewState; update: Update; changedIds: Set<string>; headingLevel?: 2 | 3 }

/** The full requirement editor in a dialog: opened from a board row. */
export function RequirementDialog({ requirement, spec, state, update, changedIds, onClose }: DialogProps) {
  if (!requirement) return null
  return (
    <Dialog isOpen onOpenChange={(open) => !open && onClose()} width={720} maxHeight="90dvh" purpose="form">
      <DialogHeader title={`${requirement.id} · ${requirement.summary}`} subtitle={requirement.area} onOpenChange={(open) => !open && onClose()} />
      <VStack padding={4}>
        <RequirementDetail requirement={requirement} spec={spec} state={state} update={update} changedIds={changedIds} />
      </VStack>
    </Dialog>
  )
}

/** Everything about one requirement plus its editable fields; a Claude-authored item shows Claude's call but never preselects it. */
export function RequirementDetail({ requirement, spec, state, update, changedIds, headingLevel }: DetailProps) {
  const awaiting = isAwaitingCall(state, requirement)
  const baseline = placementInSpec(requirement)
  const placement = effectivePlacement(state, requirement)
  const moved = requirementMoved(state, requirement)
  const warnings = scopeWarnings(state, spec).filter((message) => message.includes(requirement.id))
  const dependents = spec.requirements.filter((candidate) => candidate.dependsOn.includes(requirement.id)).map((candidate) => candidate.id)
  const assumptions = spec.assumptions.filter((assumption) => assumption.affects.includes(requirement.id))

  const guard = useScopeOutGuard()
  const [isChoosingCondition, setIsChoosingCondition] = useState(false)
  const commitScope = (target: Placement, nextCondition?: ScopeCondition) => {
    const apply = () => setPlacement(update, requirement, baseline, target, nextCondition)
    if (target === 'out') guard(spec, state, requirement, apply)
    else apply()
  }
  const setScope = (value: string) => {
    setIsChoosingCondition(value === 'conditional')
    if (value === 'in' || value === 'out') commitScope(value)
  }
  const scopeValue = isChoosingCondition || placement === 'conditional' ? 'conditional' : placement === undefined ? '' : placement

  return (
    <VStack gap={4}>
      {headingLevel ? (
        <VStack gap={0.5}>
          <HStack gap={1} align="center" wrap="wrap">
            <Text type="label" color="secondary">{requirement.id} · {requirement.area}</Text>
            <ChangedToken id={requirement.id} changedIds={changedIds} />
          </HStack>
          <Heading level={headingLevel}>{requirement.summary}</Heading>
        </VStack>
      ) : (
        <ChangedToken id={requirement.id} changedIds={changedIds} />
      )}
      <ClaudeField label="What this means">{requirement.detail}</ClaudeField>
      <VStack gap={1}>
        <Text type="label" color="secondary">Spec wording</Text>
        <SpecMarkdown compact>{`> ${requirement.text}`}</SpecMarkdown>
      </VStack>

      {requirement.provenance === 'claude' ? (
        <Banner
          status="info"
          title={`Claude recommends ${CHOICE_LABEL[baseline]} · ${GROUP_LABEL[requirement.group]}`}
          description={
            requirement.rationale ? (
              <VStack gap={1}>
                <SpecMarkdown compact>{requirement.rationale}</SpecMarkdown>
                {awaiting ? <Text type="supporting">Nothing is preselected: decide below whether it is in scope.</Text> : null}
              </VStack>
            ) : undefined
          }
          collapsible={false}
        />
      ) : null}

      {warnings.length > 0 ? (
        <Banner status="warning" title="Scope problem" collapsible={false}>
          <VStack gap={1}>
            {warnings.map((message) => <Text key={message}>{message}</Text>)}
          </VStack>
        </Banner>
      ) : null}

      <Divider />
      <RadioList label="Scope" orientation="horizontal" value={scopeValue} onChange={setScope}>
        <RadioListItem value="in" label={CHOICE_LABEL.in} description={`Goes in Claude's ${GROUP_LABEL[requirement.group]} group`} />
        <RadioListItem value="conditional" label={CHOICE_LABEL.conditional} description="Kept only while it stays within its code budget" />
        <RadioListItem value="out" label={CHOICE_LABEL.out} description="Deliberately not built" />
      </RadioList>
      {scopeValue === 'conditional' ? (
        <Selector
          label="Condition"
          placeholder="Choose how much code it may cost"
          value={effectiveCondition(state, requirement)}
          onChange={(value) => commitScope('conditional', value as ScopeCondition)}
          options={CONDITIONS.map((condition) => ({ value: condition, label: CONDITION_LABEL[condition] }))}
        />
      ) : null}
      {moved ? (
        <TextArea
          label={`Proposed as ${CHOICE_LABEL[baseline]}${requirement.condition ? ` · ${CONDITION_LABEL[requirement.condition]}` : ''}. Why the change?`}
          rows={2}
          value={state.moveReasons[requirement.id] ?? ''}
          onChange={(reason) => update((s) => ({ ...s, moveReasons: { ...s.moveReasons, [requirement.id]: reason } }), requirement.id)}
          isRequired
        />
      ) : null}
      <TextArea
        label="Your note"
        isOptional
        rows={2}
        value={state.notes[requirement.id] ?? ''}
        onChange={(note) => update((s) => ({ ...s, notes: { ...s.notes, [requirement.id]: note } }), requirement.id)}
      />

      <Divider />
      <MetadataList columns="multi">
        <MetadataListItem label="Where it came from"><ProvenanceToken requirement={requirement} /></MetadataListItem>
        {requirement.question ? <MetadataListItem label="Brainstorm question">{requirement.question}</MetadataListItem> : null}
        {requirement.certainty ? <MetadataListItem label="How sure we are"><CertaintyToken certainty={requirement.certainty} /></MetadataListItem> : null}
        <MetadataListItem label="Depends on">{requirement.dependsOn.join(', ') || 'Nothing'}</MetadataListItem>
        <MetadataListItem label="Needed by">{dependents.join(', ') || 'Nothing'}</MetadataListItem>
        {assumptions.length > 0 ? <MetadataListItem label="Rests on">{assumptions.map((assumption) => assumption.id).join(', ')}</MetadataListItem> : null}
      </MetadataList>
      {assumptions.length > 0 ? (
        <VStack gap={1}>
          {assumptions.map((assumption) => (
            <Text key={assumption.id} type="supporting">{assumption.id}: {assumption.claim}</Text>
          ))}
        </VStack>
      ) : null}
    </VStack>
  )
}
