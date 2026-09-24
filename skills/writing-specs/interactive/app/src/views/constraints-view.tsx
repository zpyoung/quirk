import { useState } from 'react'
import { Button } from '@astryxdesign/core/Button'
import { Heading } from '@astryxdesign/core/Heading'
import { HStack, VStack } from '@astryxdesign/core/Layout'
import { List, ListItem } from '@astryxdesign/core/List'
import { RadioList, RadioListItem } from '@astryxdesign/core/RadioList'
import { Text } from '@astryxdesign/core/Text'
import { TextArea } from '@astryxdesign/core/TextArea'
import { Token } from '@astryxdesign/core/Token'
import type { Constraint, ConstraintRulingVerb, LogicSpec } from '../spec-types'
import { CONSTRAINT_KIND_LABEL, CONSTRAINT_RULING_LABEL, nextConstraintRuling } from '../review-state'
import { ChangedToken, ClaudeField, PreselectedToken, ProvenanceToken, SpecMarkdown } from './shared'
import { ListDetailRegister, nextOpenEntryId } from './list-detail-register'
import type { ViewProps } from './view-props'

const RULING_COLOR: Record<ConstraintRulingVerb, 'green' | 'yellow' | 'red'> = { approve: 'green', rewrite: 'yellow', reject: 'red' }
const FOLDED_RULING_COLOR: Record<'approved' | 'rewritten' | 'rejected', 'green' | 'yellow' | 'red'> = { approved: 'green', rewritten: 'yellow', rejected: 'red' }
const FOLDED_RULING_LABEL: Record<'approved' | 'rewritten' | 'rejected', string> = { approved: 'Approved', rewritten: 'Rewritten', rejected: 'Rejected' }

function constraintDecided(props: ViewProps, constraint: Constraint): boolean {
  const entry = props.state.constraintRulings[constraint.id]
  if (!entry) return false
  if (entry.ruling === 'rewrite') return Boolean(entry.text.trim())
  if (entry.ruling === 'reject') return Boolean(entry.reason.trim())
  return entry.ruling === 'approve'
}

function ConstraintDetail({ constraint, props, onApprove }: { constraint: Constraint; props: ViewProps; onApprove: () => void }) {
  const { state, update, changedIds } = props
  const isClaude = constraint.provenance === 'claude'
  const entry = state.constraintRulings[constraint.id]
  const hasEntry = entry !== undefined
  const ruling = entry?.ruling ?? (isClaude ? 'approve' : undefined)
  const text = entry?.text ?? constraint.text
  const reason = entry?.reason ?? ''
  const set = (patch: { ruling?: ConstraintRulingVerb; text?: string; reason?: string }) => {
    update((s) => ({
      ...s,
      constraintRulings: {
        ...s.constraintRulings,
        [constraint.id]: nextConstraintRuling(entry, constraint.text, isClaude, patch),
      },
    }), constraint.id)
    if (patch.ruling === 'approve') onApprove()
  }

  return (
    <VStack gap={3}>
      <HStack gap={2} align="center" wrap="wrap">
        <Text type="label" color="secondary">{constraint.id}</Text>
        <ChangedToken id={constraint.id} changedIds={changedIds} />
        <Token size="sm" label={CONSTRAINT_KIND_LABEL[constraint.kind]} />
        <ProvenanceToken item={constraint} />
        {isClaude && !hasEntry ? <PreselectedToken /> : null}
      </HStack>
      <SpecMarkdown>{constraint.text}</SpecMarkdown>
      {constraint.rationale ? <ClaudeField label="Why this constraint">{constraint.rationale}</ClaudeField> : null}
      <RadioList label="Your ruling" orientation="horizontal" value={ruling ?? ''} onChange={(value) => set({ ruling: value as ConstraintRulingVerb })}>
        <RadioListItem value="approve" label="Approve" description="Keep it as written" />
        <RadioListItem value="rewrite" label="Rewrite" description="Write it in your own words" />
        <RadioListItem value="reject" label="Reject" description="Needs a written reason" />
      </RadioList>
      {isClaude && !hasEntry ? (
        // re-clicking the already-selected Approve radio fires no change event, so the preselected pick needs its own confirm action
        <Button size="sm" variant="secondary" label="Confirm Approve" onClick={() => set({ ruling: 'approve' })} />
      ) : null}
      {ruling === 'rewrite' ? <TextArea label="Your wording" rows={3} value={text} onChange={(value) => set({ text: value })} isRequired /> : null}
      {ruling === 'reject' ? <TextArea label="Why reject it?" rows={3} value={reason} onChange={(value) => set({ reason: value })} isRequired /> : null}
    </VStack>
  )
}

function ConstraintRegister({ props }: { props: ViewProps }) {
  const { spec, state } = props
  const [selectedId, setSelectedId] = useState<string | undefined>(
    () => spec.constraints.find((c) => !constraintDecided(props, c))?.id ?? spec.constraints[0]?.id,
  )
  const selected = spec.constraints.find((c) => c.id === selectedId) ?? spec.constraints[0]
  if (!selected) return <Text type="supporting">The spec lists no constraints.</Text>
  const entries = spec.constraints.map((c) => {
    const entry = state.constraintRulings[c.id]
    const isDone = constraintDecided(props, c)
    return {
      id: c.id,
      label: `${c.id} · ${CONSTRAINT_KIND_LABEL[c.kind]}`,
      description: c.text,
      isDone,
      status: isDone && entry
        ? <Token size="sm" color={RULING_COLOR[entry.ruling]} label={CONSTRAINT_RULING_LABEL[entry.ruling]} />
        : <Token size="sm" color="blue" label="To rule" />,
    }
  })
  // rewrite and reject count as ruled on their first keystroke, so only approval advances the selection
  const selectNextAfter = (id: string) => {
    const nextId = nextOpenEntryId(entries, id)
    if (nextId) setSelectedId(nextId)
  }
  return (
    <ListDetailRegister
      intro="Non-behavioral requirements — placement, verification, naming, non-goals — reviewed one at a time; ruled ones move to the end. Approve as written, rewrite in your own words, or reject with a reason. There is no approve-all."
      doneLabel="ruled"
      listLabel="Constraints"
      nextLabel="Next to rule"
      entries={entries}
      selectedId={selected.id}
      onSelect={setSelectedId}
      detail={<ConstraintDetail constraint={selected} props={props} onApprove={() => selectNextAfter(selected.id)} />}
    />
  )
}

function ConstraintsReadOnly({ spec }: { spec: LogicSpec }) {
  return (
    <VStack gap={4}>
      <Heading level={2}>Constraints</Heading>
      <Text type="supporting" as="p">Ruled during stage 1; shown here read-only for reference.</Text>
      <List hasDividers>
        {spec.constraints.map((c) => (
          <ListItem
            key={c.id}
            label={`${c.id} · ${CONSTRAINT_KIND_LABEL[c.kind]}`}
            description={c.originalText ? `${c.text} (Originally: ${c.originalText})` : c.text}
            startContent={c.ruling ? <Token size="sm" color={FOLDED_RULING_COLOR[c.ruling]} label={FOLDED_RULING_LABEL[c.ruling]} /> : null}
            endContent={c.rejectReason ? <Text type="supporting">{c.rejectReason}</Text> : null}
          />
        ))}
      </List>
    </VStack>
  )
}

/** One constraint at a time — approve, rewrite, or reject; read-only in stage 2. */
export function ConstraintsView(props: ViewProps) {
  const { spec } = props
  if (spec.stage === 2) return <ConstraintsReadOnly spec={spec} />
  return (
    <VStack gap={3}>
      <Heading level={2}>Constraints</Heading>
      <Text type="supporting" as="p">
        Non-behavioral requirements a scenario cannot express — placement, verification, naming, non-goals.
      </Text>
      <ConstraintRegister props={props} />
    </VStack>
  )
}
