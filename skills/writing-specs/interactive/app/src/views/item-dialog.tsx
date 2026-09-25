import type { ReactNode } from 'react'
import { Dialog, DialogHeader } from '@astryxdesign/core/Dialog'
import { HStack, VStack } from '@astryxdesign/core/Layout'
import { Text } from '@astryxdesign/core/Text'
import type { LogicSpec, ReviewState, Scenario } from '../spec-types'
import { CONSTRAINT_KIND_LABEL, CONSTRAINT_RULING_LABEL, RULINGS, effectiveCertainty, scenarioThen } from '../review-state'
import { CertaintyToken, ClaudeField, Field, ItemReference, SpecMarkdown } from './shared'

type Details = { kind: string; title: string; body: ReactNode }

function scenarioDecision(spec: LogicSpec, state: ReviewState, scenario: Scenario): string {
  const { id, dropReason } = scenario
  if (dropReason) return `Dropped: ${dropReason}`
  // stage 2 keeps no approval state for folded scenarios; only a reopened one is still undecided
  if (spec.stage === 2 && !scenario.reopened) return 'Approved'
  if (state.scenarioDrops[id]?.trim()) return `Dropped: ${state.scenarioDrops[id]}`
  if (state.scenarioUpdates[id]?.trim()) return `Update requested: ${state.scenarioUpdates[id]}`
  return state.scenarioApproved[id] ? 'Approved' : 'Not decided yet'
}

function details(spec: LogicSpec, state: ReviewState, id: string): Details | null {
  const behavior = spec.behaviors.find((item) => item.id === id)
  if (behavior) {
    const scenarios = spec.scenarios.filter((s) => s.behavior === id)
    return {
      kind: 'Behavior',
      title: behavior.rule,
      body: (
        <>
          {behavior.detail ? <SpecMarkdown>{behavior.detail}</SpecMarkdown> : null}
          <Field label={`Scenarios (${scenarios.length})`}>
            <VStack gap={1}>{scenarios.map((s) => <ItemReference key={s.id} spec={spec} id={s.id} />)}</VStack>
          </Field>
        </>
      ),
    }
  }
  const scenario = spec.scenarios.find((item) => item.id === id)
  if (scenario) {
    return {
      kind: 'Scenario',
      title: spec.behaviors.find((b) => b.id === scenario.behavior)?.rule ?? scenario.behavior,
      body: (
        <>
          <SpecMarkdown>{`**Given** ${scenario.given}\n\n**When** ${scenario.when}\n\n**Then** ${scenarioThen(state, scenario)}`}</SpecMarkdown>
          <ClaudeField label="Why">{scenario.explanation}</ClaudeField>
          <Field label="Your decision">{scenarioDecision(spec, state, scenario)}</Field>
        </>
      ),
    }
  }
  const constraint = spec.constraints.find((item) => item.id === id)
  if (constraint) {
    const entry = state.constraintRulings[id]
    const ruling = constraint.ruling
      ? { approved: 'Approved', rewritten: 'Rewritten', rejected: 'Rejected' }[constraint.ruling]
      : entry ? CONSTRAINT_RULING_LABEL[entry.ruling] : 'Not ruled yet'
    return {
      kind: `Constraint · ${CONSTRAINT_KIND_LABEL[constraint.kind]}`,
      title: constraint.area,
      body: (
        <>
          <SpecMarkdown>{constraint.text}</SpecMarkdown>
          {constraint.rationale ? <ClaudeField label="Why this constraint">{constraint.rationale}</ClaudeField> : null}
          <Field label="Your ruling">{ruling}</Field>
        </>
      ),
    }
  }
  const assumption = spec.assumptions.find((item) => item.id === id)
  if (assumption) {
    const ruling = assumption.ruling ?? state.assumptions[id]?.ruling
    const note = assumption.rulingNote ?? state.assumptions[id]?.note
    return {
      kind: 'Assumption',
      title: assumption.claim,
      body: (
        <>
          <HStack><CertaintyToken certainty={effectiveCertainty(state, assumption)} /></HStack>
          <Field label="Why we think so">{assumption.basis}</Field>
          <ClaudeField label="What this means">{assumption.meaning}</ClaudeField>
          <Field label="If this is wrong">{assumption.ifWrong}</Field>
          <Field label="Your ruling">{ruling ? (RULINGS.find((r) => r.value === ruling)?.label ?? ruling) : 'Not ruled yet'}</Field>
          {note?.trim() ? <Field label="Your note">{note}</Field> : null}
        </>
      ),
    }
  }
  const spot = spec.blindSpots.find((item) => item.id === id)
  if (spot) {
    const acceptance = spot.acceptance ?? (state.blindSpots[id]?.accepted ? state.blindSpots[id].note : undefined)
    return {
      kind: 'Blind spot',
      title: spot.title,
      body: (
        <>
          <ClaudeField label="What could go wrong">{spot.detail}</ClaudeField>
          {spot.sources.length ? (
            <Field label="Caused by">
              <VStack gap={1}>{spot.sources.map((source) => <ItemReference key={source} spec={spec} id={source} />)}</VStack>
            </Field>
          ) : null}
          {spot.resolvedBy ? <Field label="Resolved once decided"><ItemReference spec={spec} id={spot.resolvedBy} /></Field> : null}
          <Field label="Your acceptance">{acceptance?.trim() ? acceptance : 'Not accepted'}</Field>
        </>
      ),
    }
  }
  return null
}

/** Read-only details for a non-requirement item referenced by ID elsewhere in the review; links inside it swap to the linked item. */
export function ItemDialog({ id, spec, state, onClose }: { id: string | null; spec: LogicSpec; state: ReviewState; onClose: () => void }) {
  const item = id ? details(spec, state, id) : null
  if (!id || !item) return null
  return (
    <Dialog isOpen onOpenChange={(open) => !open && onClose()} width={720}>
      <DialogHeader title={`${id} · ${item.title}`} subtitle={item.kind} onOpenChange={(open) => !open && onClose()} />
      <VStack gap={3} padding={4}>
        {item.body}
        {spec.stage === 1 ? <Text type="supporting">Decide this item on its own tab; this view is for reference.</Text> : null}
      </VStack>
    </Dialog>
  )
}
