import { useState } from 'react'
import { Banner } from '@astryxdesign/core/Banner'
import { Button } from '@astryxdesign/core/Button'
import { Dialog, DialogHeader } from '@astryxdesign/core/Dialog'
import { Divider } from '@astryxdesign/core/Divider'
import { Heading } from '@astryxdesign/core/Heading'
import { Card, HStack, VStack } from '@astryxdesign/core/Layout'
import { MetadataList, MetadataListItem } from '@astryxdesign/core/MetadataList'
import { RadioList, RadioListItem } from '@astryxdesign/core/RadioList'
import { Selector } from '@astryxdesign/core/Selector'
import { Text } from '@astryxdesign/core/Text'
import { TextArea } from '@astryxdesign/core/TextArea'
import { Token } from '@astryxdesign/core/Token'
import type { DisputeKind, LogicSpec, Placement, Requirement, ReviewState, ScopeCondition } from '../spec-types'
import {
  CHOICE_LABEL,
  CONDITION_LABEL,
  CONSTRAINT_KIND_LABEL,
  GROUP_LABEL,
  effectiveCondition,
  effectivePlacement,
  placementInSpec,
  requirementMoved,
  scopeWarnings,
  type Update,
} from '../review-state'
import { ChangedToken, CertaintyToken, ClaudeField, SpecMarkdown } from './shared'
import { CONDITIONS, setPlacement } from './board-model'
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
        {/* keyed by id so switching requirements without closing the dialog resets the dispute draft below */}
        <RequirementDetail key={requirement.id} requirement={requirement} spec={spec} state={state} update={update} changedIds={changedIds} />
      </VStack>
    </Dialog>
  )
}

/** One `derivedFrom` source shown inline: a scenario's behavior rule and Given / When / Then, or a constraint's kind and text. */
function DerivedFromSource({ id, spec }: { id: string; spec: LogicSpec }) {
  const scenario = spec.scenarios.find((s) => s.id === id)
  if (scenario) {
    const behavior = spec.behaviors.find((b) => b.id === scenario.behavior)
    return (
      <Card padding={2}>
        <VStack gap={1}>
          <HStack gap={1} align="center" wrap="wrap">
            <Text type="label" color="secondary">{id}</Text>
            {scenario.reopened ? <Token size="sm" color="orange" label="Reopened" description={scenario.reopened.reason} /> : null}
          </HStack>
          {behavior ? <Text type="supporting">{behavior.rule}</Text> : null}
          <Text>{`Given ${scenario.given}`}</Text>
          <Text>{`When ${scenario.when}`}</Text>
          <Text>{`Then ${scenario.then}`}</Text>
        </VStack>
      </Card>
    )
  }
  const constraint = spec.constraints.find((c) => c.id === id)
  if (constraint) {
    return (
      <Card padding={2}>
        <VStack gap={1}>
          <HStack gap={1} align="center" wrap="wrap">
            <Text type="label" color="secondary">{id}</Text>
            <Token size="sm" label={CONSTRAINT_KIND_LABEL[constraint.kind]} />
          </HStack>
          <Text>{constraint.text}</Text>
        </VStack>
      </Card>
    )
  }
  return <Text type="supporting">{id}</Text>
}

function DerivedFromSources({ requirement, spec }: { requirement: Requirement; spec: LogicSpec }) {
  if (requirement.derivedFrom.length === 0) return <Text type="supporting">Nothing.</Text>
  return (
    <VStack gap={2}>
      {requirement.derivedFrom.map((id) => <DerivedFromSource key={id} id={id} spec={spec} />)}
    </VStack>
  )
}

/** `CONTRACT:` dispute kind `derivation` | `scenario`, a required reason, and — for `scenario` — a target from the requirement's `derivedFrom` scenario ids (see Disputes). Saving writes `state.disputes[requirementId]`; withdrawing deletes it. */
function DisputeControl({ requirement, spec, state, update }: { requirement: Requirement; spec: LogicSpec; state: ReviewState; update: Update }) {
  const scenarioTargets = requirement.derivedFrom.filter((id) => spec.scenarios.some((s) => s.id === id))
  const existing = state.disputes[requirement.id]
  const [kind, setKind] = useState<DisputeKind>(existing?.kind ?? 'derivation')
  const [target, setTarget] = useState<string>(existing?.target ?? scenarioTargets[0] ?? '')
  const [reason, setReason] = useState(existing?.reason ?? '')
  const canSave = Boolean(reason.trim()) && (kind !== 'scenario' || Boolean(target))

  const save = () => {
    const value = { kind, target: kind === 'scenario' ? target : null, reason: reason.trim() }
    update((s) => ({ ...s, disputes: { ...s.disputes, [requirement.id]: value } }), requirement.id)
  }
  const withdraw = () => {
    update((s) => {
      const disputes = { ...s.disputes }
      delete disputes[requirement.id]
      return { ...s, disputes }
    }, requirement.id)
    setReason('')
  }

  return (
    <VStack gap={2}>
      <Heading level={4}>Dispute</Heading>
      {existing ? (
        <Banner
          status="warning"
          title="Dispute recorded"
          description={
            existing.kind === 'scenario'
              ? 'Re-approve the reopened scenario above; Claude then runs `reapprove` and re-derives this requirement.'
              : "Claude rewrites this requirement's text; stage 1 and its pin are untouched."
          }
          collapsible={false}
        />
      ) : null}
      <RadioList label="What are you disputing?" value={kind} onChange={(value) => setKind(value as DisputeKind)}>
        <RadioListItem value="derivation" label="The derivation" description="This requirement shouldn't exist as derived, or is derived wrong." />
        <RadioListItem value="scenario" label="A specific scenario" description="One of the scenarios behind this requirement needs another look." />
      </RadioList>
      {kind === 'scenario' ? (
        <Selector
          label="Which scenario?"
          placeholder="Choose a scenario"
          value={target}
          onChange={setTarget}
          options={scenarioTargets.map((id) => ({ value: id, label: id }))}
          isDisabled={scenarioTargets.length === 0}
        />
      ) : null}
      <TextArea label="Reason" rows={3} value={reason} onChange={setReason} isRequired />
      <HStack gap={2} wrap="wrap">
        <Button variant="primary" label={existing ? 'Update dispute' : 'Raise dispute'} isDisabled={!canSave} onClick={save} />
        {existing ? <Button variant="secondary" label="Withdraw dispute" onClick={withdraw} /> : null}
      </HStack>
    </VStack>
  )
}

/** Everything about one requirement plus its editable fields. */
export function RequirementDetail({ requirement, spec, state, update, changedIds, headingLevel }: DetailProps) {
  const baseline = placementInSpec(requirement)
  const placement = effectivePlacement(state, requirement)
  const moved = requirementMoved(state, requirement)
  const warnings = scopeWarnings(state, spec).filter((message) => message.includes(requirement.id))
  const dependents = spec.requirements.filter((candidate) => candidate.dependsOn.includes(requirement.id)).map((candidate) => candidate.id)
  const derivedFromSet = new Set(requirement.derivedFrom)
  const assumptions = spec.assumptions.filter((assumption) => assumption.affects.some((id) => derivedFromSet.has(id)))
  const blindSpots = spec.blindSpots.filter((spot) => spot.sources.some((id) => derivedFromSet.has(id)))

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
  const scopeValue = isChoosingCondition || placement === 'conditional' ? 'conditional' : placement

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
      <VStack gap={2}>
        <Text type="label" color="secondary">Derived from</Text>
        <DerivedFromSources requirement={requirement} spec={spec} />
      </VStack>

      <Divider />
      <MetadataList columns="multi">
        {requirement.certainty ? <MetadataListItem label="How sure we are"><CertaintyToken certainty={requirement.certainty} /></MetadataListItem> : null}
        <MetadataListItem label="Depends on">{requirement.dependsOn.join(', ') || 'Nothing'}</MetadataListItem>
        <MetadataListItem label="Needed by">{dependents.join(', ') || 'Nothing'}</MetadataListItem>
        {assumptions.length > 0 || blindSpots.length > 0 ? (
          <MetadataListItem label="Rests on">{[...assumptions.map((a) => a.id), ...blindSpots.map((b) => b.id)].join(', ')}</MetadataListItem>
        ) : null}
      </MetadataList>
      {assumptions.length > 0 || blindSpots.length > 0 ? (
        <VStack gap={1}>
          {assumptions.map((assumption) => (
            <Text key={assumption.id} type="supporting">{assumption.id}: {assumption.claim}</Text>
          ))}
          {blindSpots.map((spot) => (
            <Text key={spot.id} type="supporting">{spot.id}: {spot.title}</Text>
          ))}
        </VStack>
      ) : null}

      <Divider />
      <DisputeControl requirement={requirement} spec={spec} state={state} update={update} />
    </VStack>
  )
}
