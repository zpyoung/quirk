import { useState, type ReactNode } from 'react'
import { Banner } from '@astryxdesign/core/Banner'
import { Button } from '@astryxdesign/core/Button'
import { CheckboxInput } from '@astryxdesign/core/CheckboxInput'
import { Dialog, DialogHeader } from '@astryxdesign/core/Dialog'
import { Heading } from '@astryxdesign/core/Heading'
import { Card, HStack, VStack } from '@astryxdesign/core/Layout'
import { Link } from '@astryxdesign/core/Link'
import { RadioList, RadioListItem } from '@astryxdesign/core/RadioList'
import { Text } from '@astryxdesign/core/Text'
import { TextArea } from '@astryxdesign/core/TextArea'
import { Token } from '@astryxdesign/core/Token'
import type { Assumption, AssumptionRuling, BlindSpot, LogicSpec, ResearchRequest } from '../spec-types'
import { RULINGS, activeBlindSpots, pendingResearchRequests, requestId, type Update } from '../review-state'
import { CERTAINTY_LABEL, CertaintyToken, ChangedToken, ClaudeField, ClaudeWroteToken, Field, SpecMarkdown } from './shared'
import { ListDetailRegister } from './list-detail-register'
import type { ViewProps } from './view-props'

const RULING_COLOR: Record<AssumptionRuling, 'green' | 'yellow' | 'red'> = { 'build-on': 'green', 'verify-first': 'yellow', wrong: 'red' }

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <VStack gap={1}>
      <Text type="label" color="secondary">{title}</Text>
      {children}
    </VStack>
  )
}

/** A scenario or constraint's short label for referencing it from an assumption or blind spot. */
function itemLabel(spec: LogicSpec, id: string): string {
  const scenario = spec.scenarios.find((s) => s.id === id)
  if (scenario) return scenario.then
  const constraint = spec.constraints.find((c) => c.id === id)
  if (constraint) return constraint.text
  return id
}

function resolutionHint(spec: LogicSpec, resolvedBy: string): string {
  return spec.scenarios.some((s) => s.id === resolvedBy) ? 'once approved and not dropped' : 'once approved or rewritten'
}

function AssumptionDetail({ assumption, props, readOnly }: { assumption: Assumption; props: ViewProps; readOnly: boolean }) {
  const { spec, state, update, changedIds } = props
  // stage 2 shows the ruling folded into the spec, not the fresh (empty) stage-2 review state
  const entry = readOnly ? { ruling: assumption.ruling, note: assumption.rulingNote ?? '' } : (state.assumptions[assumption.id] ?? { note: '' })
  const set = (patch: Partial<typeof entry>) =>
    update((s) => ({ ...s, assumptions: { ...s.assumptions, [assumption.id]: { ...entry, ...patch } } }), assumption.id)
  const needsNote = entry.ruling === 'verify-first' || entry.ruling === 'wrong'
  return (
    <VStack gap={3}>
      <HStack gap={2} align="center" wrap="wrap">
        <Text type="label" color="secondary">{assumption.id}</Text>
        <ChangedToken id={assumption.id} changedIds={changedIds} />
        <CertaintyToken certainty={assumption.certainty} />
      </HStack>
      <Heading level={3}>{assumption.claim}</Heading>
      <Field label="Why we think so">{assumption.basis}</Field>
      <ClaudeField label="What this means">{assumption.meaning}</ClaudeField>
      <Field label="If this is wrong">{assumption.ifWrong}</Field>
      <Section title={`Scenarios and constraints that rest on it (${assumption.affects.length})`}>
        {assumption.affects.length
          ? assumption.affects.map((id) => <Text key={id}>{`${id} · ${itemLabel(spec, id)}`}</Text>)
          : <Text type="supporting">None.</Text>}
      </Section>
      <ClaudeField label="How to check it">{assumption.check}</ClaudeField>
      <HStack>
        <Token size="sm" color="blue" label={`Cost: ${assumption.checkCost}`} />
      </HStack>
      {readOnly ? (
        entry.ruling ? (
          <Field label="Your ruling">{RULINGS.find((r) => r.value === entry.ruling)?.label ?? entry.ruling}</Field>
        ) : (
          <Text type="supporting">Not ruled on.</Text>
        )
      ) : (
        <>
          <RadioList
            label="Your ruling"
            orientation="horizontal"
            size="sm"
            value={entry.ruling ?? ''}
            onChange={(value) => set({ ruling: value as AssumptionRuling })}
          >
            {RULINGS.map((ruling) => <RadioListItem key={ruling.value} value={ruling.value} label={ruling.label} />)}
          </RadioList>
          {needsNote ? <TextArea label="Why this ruling?" rows={3} value={entry.note} onChange={(note) => set({ note })} isRequired /> : null}
        </>
      )}
    </VStack>
  )
}

function ResearchDialog({ spot, existing, onClose, update }: { spot: BlindSpot; existing?: ResearchRequest; onClose: () => void; update: Update }) {
  const [question, setQuestion] = useState(existing?.question ?? '')
  const save = () => {
    const request: ResearchRequest = existing
      ? { ...existing, question: question.trim() }
      : { id: requestId('research'), blindSpotId: spot.id, question: question.trim(), requestedAt: new Date().toISOString() }
    update((s) => ({ ...s, researchRequests: [...s.researchRequests.filter((r) => r.id !== request.id), request] }), spot.id)
    onClose()
  }
  return (
    <Dialog isOpen onOpenChange={(open) => !open && onClose()} width={640} purpose="form">
      <DialogHeader title={`Research ${spot.id} more deeply`} subtitle={spot.title} onOpenChange={(open) => !open && onClose()} />
      <VStack gap={3} padding={4}>
        <Text type="supporting">Claude researches it with the spec and code in view, and posts findings back under this blind spot.</Text>
        <TextArea
          label="What should Claude find out? (optional)"
          rows={4}
          value={question}
          onChange={setQuestion}
          placeholder="e.g. How often does this situation come up in practice?"
        />
        <HStack gap={2} justify="end">
          <Button variant="secondary" label="Cancel" onClick={onClose} />
          <Button variant="primary" label={existing ? 'Save changes' : 'Send to Claude'} onClick={save} />
        </HStack>
      </VStack>
    </Dialog>
  )
}

/** Asks Claude to research a blind spot, then shows the pending request or Claude's findings. */
function BlindSpotResearch({ spot, props, readOnly }: { spot: BlindSpot; props: ViewProps; readOnly: boolean }) {
  const { spec, state, update } = props
  const [isAsking, setIsAsking] = useState(false)
  const answered = spec.research.filter((finding) => finding.blindSpotId === spot.id)
  const pending = pendingResearchRequests(state, spec).find((request) => request.blindSpotId === spot.id)
  if (readOnly && answered.length === 0) return null
  return (
    <Section title="Deeper research">
      {answered.map((finding) => (
        <Card key={finding.requestId} variant="blue" padding={3}>
          <VStack gap={1}>
            <HStack gap={1} align="center" wrap="wrap">
              <Text type="label">{`Findings · ${new Date(finding.answeredAt).toLocaleDateString()}`}</Text>
              <ClaudeWroteToken />
            </HStack>
            <Text weight="semibold">{finding.summary}</Text>
            <SpecMarkdown compact>{finding.detail}</SpecMarkdown>
          </VStack>
        </Card>
      ))}
      {readOnly ? null : pending ? (
        <Banner
          status="info"
          title="Waiting for Claude"
          description={pending.question ? `You asked: ${pending.question}` : 'You asked for a general deeper look.'}
          collapsible={false}
        >
          <HStack gap={3}>
            <Link onClick={() => setIsAsking(true)}>Change the question</Link>
            <Link onClick={() => update((s) => ({ ...s, researchRequests: s.researchRequests.filter((r) => r.id !== pending.id) }))}>Cancel the request</Link>
          </HStack>
        </Banner>
      ) : (
        <HStack>
          <Button
            variant="secondary"
            label={answered.length > 0 ? 'Ask Claude to dig further' : 'Ask Claude to research this'}
            onClick={() => setIsAsking(true)}
          />
        </HStack>
      )}
      {isAsking ? <ResearchDialog spot={spot} existing={pending} onClose={() => setIsAsking(false)} update={update} /> : null}
    </Section>
  )
}

/** A blind spot's full detail: what it means, its sources, research, and — while active and editable — the acceptance controls. */
export function BlindSpotDetail({ spot, props }: { spot: BlindSpot; props: ViewProps }) {
  const { spec, state, update, changedIds } = props
  const readOnly = spec.stage === 2
  const isActive = activeBlindSpots(state, spec).some((s) => s.id === spot.id)
  // stage 2 shows the acceptance folded into the spec, not the fresh (empty) stage-2 review state
  const entry = readOnly ? { accepted: Boolean(spot.acceptance), note: spot.acceptance ?? '' } : (state.blindSpots[spot.id] ?? { accepted: false, note: '' })
  const set = (patch: Partial<typeof entry>) => update((s) => ({ ...s, blindSpots: { ...s.blindSpots, [spot.id]: { ...entry, ...patch } } }), spot.id)
  return (
    <VStack gap={3}>
      <HStack gap={2} align="center" wrap="wrap">
        <Text type="label" color="secondary">{spot.id}</Text>
        <ChangedToken id={spot.id} changedIds={changedIds} />
        {isActive ? <Token size="sm" color="blue" label="Active" /> : <Token size="sm" color="default" label="Resolved" />}
      </HStack>
      <Heading level={3}>{spot.title}</Heading>
      <ClaudeField label="What could go wrong">{spot.detail}</ClaudeField>
      <Section title="Caused by">
        {spot.sources.length
          ? spot.sources.map((id) => <Text key={id}>{`${id} · ${itemLabel(spec, id)}`}</Text>)
          : <Text type="supporting">Nothing in particular.</Text>}
      </Section>
      {spot.resolvedBy ? (
        <Field label="Resolved once decided">{`${spot.resolvedBy} · ${itemLabel(spec, spot.resolvedBy)}, ${resolutionHint(spec, spot.resolvedBy)}`}</Field>
      ) : null}
      <BlindSpotResearch spot={spot} props={props} readOnly={readOnly} />
      {readOnly ? (
        entry.note ? <Field label="Your acceptance">{entry.note}</Field> : null
      ) : isActive ? (
        <>
          <TextArea label="In your own words" rows={3} value={entry.note} onChange={(note) => set({ note })} placeholder="e.g. rare in practice because…" />
          <CheckboxInput
            label="I accept this blind spot"
            value={entry.accepted}
            isDisabled={!entry.note.trim()}
            disabledMessage="Write the reason first."
            onChange={(accepted) => set({ accepted })}
          />
        </>
      ) : (
        <Text type="supporting">Resolved by an approved decision above; nothing to accept unless that changes.</Text>
      )}
    </VStack>
  )
}

function AssumptionRegister({ props, readOnly }: { props: ViewProps; readOnly: boolean }) {
  const { spec, state } = props
  // stage 2 rules on assumptions are folded into the spec, not tracked in the fresh stage-2 review state
  const rulingFor = (a: Assumption) => (readOnly ? a.ruling : state.assumptions[a.id]?.ruling)
  const [selectedId, setSelectedId] = useState<string | undefined>(
    () => spec.assumptions.find((a) => !rulingFor(a))?.id ?? spec.assumptions[0]?.id,
  )
  const selected = spec.assumptions.find((a) => a.id === selectedId) ?? spec.assumptions[0]
  if (!selected) return <Text type="supporting">The spec lists no assumptions.</Text>
  return (
    <ListDetailRegister
      intro="Each one is something the spec depends on. Confirmed means it was checked on this machine; assumed means it was reasoned from code or transcripts but never seen happening; unverified means nobody has checked yet."
      doneLabel="ruled"
      listLabel="Assumptions"
      nextLabel="Next to rule"
      entries={spec.assumptions.map((a) => {
        const ruling = rulingFor(a)
        return {
          id: a.id,
          label: `${a.id} · ${CERTAINTY_LABEL[a.certainty]}`,
          description: a.claim,
          isDone: Boolean(ruling),
          status: ruling ? (
            <Token size="sm" color={RULING_COLOR[ruling]} label={RULINGS.find((r) => r.value === ruling)?.label ?? ruling} />
          ) : (
            <Token size="sm" color="blue" label="To rule" />
          ),
        }
      })}
      selectedId={selected.id}
      onSelect={setSelectedId}
      detail={<AssumptionDetail assumption={selected} props={props} readOnly={readOnly} />}
    />
  )
}

function BlindSpotRegister({ props }: { props: ViewProps }) {
  const { spec, state } = props
  const readOnly = spec.stage === 2
  const activeIds = new Set(activeBlindSpots(state, spec).map((spot) => spot.id))
  // stage 2 shows the acceptance folded into the spec, not the fresh (empty) stage-2 review state
  const isAccepted = (id: string) => (readOnly ? Boolean(spec.blindSpots.find((b) => b.id === id)?.acceptance) : Boolean(state.blindSpots[id]?.accepted))
  const noteFor = (id: string) => (readOnly ? (spec.blindSpots.find((b) => b.id === id)?.acceptance ?? '') : (state.blindSpots[id]?.note ?? ''))
  const [selectedId, setSelectedId] = useState<string | undefined>(
    () => spec.blindSpots.find((b) => activeIds.has(b.id) && !isAccepted(b.id))?.id ?? spec.blindSpots[0]?.id,
  )
  const selected = spec.blindSpots.find((b) => b.id === selectedId) ?? spec.blindSpots[0]
  if (!selected) return <Text type="supporting">The spec lists no blind spots.</Text>
  return (
    <ListDetailRegister
      intro="Cases where the spec's behavior might surprise someone. Accepting an active blind spot takes a sentence in your own words about why it is tolerable; an approved scenario or constraint that resolves it needs no acceptance."
      doneLabel="resolved"
      listLabel="Blind spots"
      nextLabel="Next to accept"
      entries={spec.blindSpots.map((b) => {
        const active = activeIds.has(b.id)
        const noteWritten = Boolean(noteFor(b.id).trim())
        return {
          id: b.id,
          label: `${b.id} · caused by ${b.sources.join(', ')}`,
          description: b.title,
          isDone: active ? isAccepted(b.id) : true,
          status: !active ? (
            <Token size="sm" color="default" label="Resolved" />
          ) : isAccepted(b.id) ? (
            <Token size="sm" color="green" label="Accepted" />
          ) : noteWritten ? (
            <Token size="sm" color="yellow" label="Reason written" />
          ) : (
            <Token size="sm" color="blue" label="To accept" />
          ),
        }
      })}
      selectedId={selected.id}
      onSelect={setSelectedId}
      detail={<BlindSpotDetail spot={selected} props={props} />}
    />
  )
}

/** Assumptions and blind-spots registers: rule on every assumption, accept every active blind spot; read-only in stage 2. */
export function RisksView(props: ViewProps) {
  const readOnly = props.spec.stage === 2
  return (
    <VStack gap={6}>
      <VStack gap={3}>
        <Heading level={2}>Assumptions the spec stands on</Heading>
        <AssumptionRegister props={props} readOnly={readOnly} />
      </VStack>
      <VStack gap={3}>
        <Heading level={2}>Blind spots you would be accepting</Heading>
        <BlindSpotRegister props={props} />
      </VStack>
    </VStack>
  )
}
