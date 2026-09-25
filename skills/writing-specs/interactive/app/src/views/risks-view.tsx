import { useState, type ReactNode } from 'react'
import { Banner } from '@astryxdesign/core/Banner'
import { Button } from '@astryxdesign/core/Button'
import { CheckboxInput } from '@astryxdesign/core/CheckboxInput'
import { Dialog, DialogHeader } from '@astryxdesign/core/Dialog'
import { Heading } from '@astryxdesign/core/Heading'
import { Card, HStack, VStack } from '@astryxdesign/core/Layout'
import { Link } from '@astryxdesign/core/Link'
import { Table, pixel, proportional, type TableColumn } from '@astryxdesign/core/Table'
import { RadioList, RadioListItem } from '@astryxdesign/core/RadioList'
import { Text } from '@astryxdesign/core/Text'
import { TextArea } from '@astryxdesign/core/TextArea'
import { Token } from '@astryxdesign/core/Token'
import type { Assumption, AssumptionRuling, BlindSpot, Certainty, LogicSpec, ResearchRequest, ReviewState } from '../spec-types'
import { CERTAINTIES, RULINGS, activeBlindSpots, assumptionRuled, effectiveCertainty, pendingResearchRequests, requestId, researchedBlindSpotIds, type Update } from '../review-state'
import { CERTAINTY_LABEL, CertaintyToken, ChangedToken, ClaudeField, ClaudeWroteToken, Field, ItemReference, itemLabel, SpecMarkdown } from './shared'
import { ItemRef, useOpenItem } from './item-links'
import { ListDetailRegister, nextOpenEntryId } from './list-detail-register'
import type { ViewProps } from './view-props'

const RULING_COLOR: Record<AssumptionRuling, 'green' | 'yellow' | 'red'> = { 'build-on': 'green', 'verify-first': 'yellow', wrong: 'red' }

// homomorphic copies, plain enough to satisfy Table's `Record<string, unknown>` row constraint
type AssumptionRow = { [K in keyof Assumption]: Assumption[K] }
type BlindSpotRow = { [K in keyof BlindSpot]: BlindSpot[K] }

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <VStack gap={1}>
      <Text type="label" color="secondary">{title}</Text>
      {children}
    </VStack>
  )
}

type BlindSpotStatus = 'resolved' | 'accepted' | 'research-requested' | 'researched' | 'reason-written' | 'open'

type BlindSpotSets = { active: Set<string>; researched: Set<string> }

function blindSpotSets(spec: LogicSpec, state: ReviewState): BlindSpotSets {
  return { active: new Set(activeBlindSpots(state, spec).map((s) => s.id)), researched: researchedBlindSpotIds(state, spec) }
}

/** Where a blind spot stands; in stage 2 it reads the outcome folded into the spec rather than review state. */
function blindSpotStatus(spot: BlindSpot, spec: LogicSpec, state: ReviewState, sets: BlindSpotSets = blindSpotSets(spec, state)): BlindSpotStatus {
  if (!sets.active.has(spot.id)) return 'resolved'
  const decision = spec.stage === 2 ? { accepted: Boolean(spot.acceptance), note: spot.acceptance ?? '' } : state.blindSpots[spot.id]
  if (decision?.accepted && decision.note.trim()) return 'accepted'
  if (sets.researched.has(spot.id)) {
    return spec.research.some((finding) => finding.blindSpotId === spot.id) ? 'researched' : 'research-requested'
  }
  return decision?.note.trim() ? 'reason-written' : 'open'
}

function BlindSpotStatusToken({ status }: { status: BlindSpotStatus }) {
  switch (status) {
    case 'resolved': return <Token size="sm" color="default" label="Resolved" />
    case 'accepted': return <Token size="sm" color="green" label="Accepted" />
    case 'researched': return <Token size="sm" color="green" label="Researched" />
    case 'research-requested': return <Token size="sm" color="yellow" label="Research requested" />
    case 'reason-written': return <Token size="sm" color="yellow" label="Reason written" />
    case 'open': return <Token size="sm" color="blue" label="To accept" />
  }
}

function resolutionHint(spec: LogicSpec, resolvedBy: string): string {
  return spec.scenarios.some((s) => s.id === resolvedBy) ? 'once approved and not dropped' : 'once approved or rewritten'
}

function AssumptionDetail({ assumption, props, onRuled }: { assumption: Assumption; props: ViewProps; onRuled: () => void }) {
  const { spec, state, update, changedIds } = props
  const entry = state.assumptions[assumption.id] ?? { note: '' }
  const set = (patch: Partial<typeof entry>) =>
    update((s) => ({ ...s, assumptions: { ...s.assumptions, [assumption.id]: { ...entry, ...patch } } }), assumption.id)
  const needsNote = entry.ruling === 'verify-first' || entry.ruling === 'wrong'
  const certainty = effectiveCertainty(state, assumption)
  const setCertainty = (value: Certainty) =>
    update((s) => {
      const current = s.assumptions[assumption.id] ?? { note: '' }
      const { certainty: _previous, ...rest } = current
      // matching Claude's value again drops the override, so only real disagreements reach the fold
      const next = value === assumption.certainty ? rest : { ...rest, certainty: value }
      return { ...s, assumptions: { ...s.assumptions, [assumption.id]: next } }
    }, assumption.id)
  return (
    <VStack gap={3}>
      <HStack gap={2} align="center" wrap="wrap">
        <Text type="label" color="secondary">{assumption.id}</Text>
        <ChangedToken id={assumption.id} changedIds={changedIds} />
        <CertaintyToken certainty={certainty} />
      </HStack>
      <Heading level={3}>{assumption.claim}</Heading>
      <RadioList
        label="Certainty"
        orientation="horizontal"
        size="sm"
        value={certainty}
        onChange={(value) => setCertainty(value as Certainty)}
      >
        {CERTAINTIES.map((value) => (
          <RadioListItem key={value} value={value} label={CERTAINTY_LABEL[value]} description={value === assumption.certainty ? "Claude's assessment" : undefined} />
        ))}
      </RadioList>
      <Field label="Why we think so">{assumption.basis}</Field>
      <ClaudeField label="What this means">{assumption.meaning}</ClaudeField>
      <Field label="If this is wrong">{assumption.ifWrong}</Field>
      <Section title={`Scenarios and constraints that rest on it (${assumption.affects.length})`}>
        {assumption.affects.length
          ? assumption.affects.map((id) => <ItemReference key={id} spec={spec} id={id} />)
          : <Text type="supporting">None.</Text>}
      </Section>
      <ClaudeField label="How to check it">{assumption.check}</ClaudeField>
      <HStack>
        <Token size="sm" color="blue" label={`Cost: ${assumption.checkCost}`} />
      </HStack>
      <RadioList
        label="Your ruling"
        orientation="horizontal"
        size="sm"
        value={entry.ruling ?? ''}
        onChange={(value) => {
          set({ ruling: value as AssumptionRuling })
          // rulings that ask for a note keep the selection so the note can be written
          if (value === 'build-on') onRuled()
        }}
      >
        {RULINGS.map((ruling) => <RadioListItem key={ruling.value} value={ruling.value} label={ruling.label} />)}
      </RadioList>
      {needsNote ? <TextArea label="Why this ruling?" rows={3} value={entry.note} onChange={(note) => set({ note })} isRequired /> : null}
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
  // a request still open at stage-1 sign-off is folded onto the blind spot until Claude answers it
  const carried = spot.researchRequest && !answered.some((finding) => finding.requestId === spot.researchRequest?.id) ? spot.researchRequest : undefined
  if (readOnly && answered.length === 0 && !carried) return null
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
      {readOnly ? (
        carried ? <Banner status="info" title="Waiting for Claude" description={carried.question ? `You asked: ${carried.question}` : 'You asked for a general deeper look.'} collapsible={false} /> : null
      ) : pending ? (
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
export function BlindSpotDetail({ spot, props, onAccepted }: { spot: BlindSpot; props: ViewProps; onAccepted?: () => void }) {
  const { spec, state, update, changedIds } = props
  const readOnly = spec.stage === 2
  const status = blindSpotStatus(spot, spec, state)
  const isActive = status !== 'resolved'
  // stage 2 shows the acceptance folded into the spec, not the fresh (empty) stage-2 review state
  const entry = readOnly ? { accepted: Boolean(spot.acceptance), note: spot.acceptance ?? '' } : (state.blindSpots[spot.id] ?? { accepted: false, note: '' })
  const set = (patch: Partial<typeof entry>) => update((s) => ({ ...s, blindSpots: { ...s.blindSpots, [spot.id]: { ...entry, ...patch } } }), spot.id)
  return (
    <VStack gap={3}>
      <HStack gap={2} align="center" wrap="wrap">
        <Text type="label" color="secondary">{spot.id}</Text>
        <ChangedToken id={spot.id} changedIds={changedIds} />
        <BlindSpotStatusToken status={status} />
      </HStack>
      <Heading level={3}>{spot.title}</Heading>
      <ClaudeField label="What could go wrong">{spot.detail}</ClaudeField>
      <Section title="Caused by">
        {spot.sources.length
          ? spot.sources.map((id) => <ItemReference key={id} spec={spec} id={id} />)
          : <Text type="supporting">Nothing in particular.</Text>}
      </Section>
      {spot.resolvedBy ? (
        <Field label="Resolved once decided">
          <Text><ItemRef id={spot.resolvedBy} />{` · ${itemLabel(spec, spot.resolvedBy)}, ${resolutionHint(spec, spot.resolvedBy)}`}</Text>
        </Field>
      ) : null}
      <BlindSpotResearch spot={spot} props={props} readOnly={readOnly} />
      {readOnly ? (
        entry.note ? <Field label="Your acceptance">{entry.note}</Field> : null
      ) : isActive ? (
        <>
          {status === 'research-requested' || status === 'researched' ? (
            <Text type="supporting">Asking Claude to research this settles it for sign-off. You can still accept it in your own words.</Text>
          ) : null}
          <TextArea label="In your own words" rows={3} value={entry.note} onChange={(note) => set({ note })} placeholder="e.g. rare in practice because…" />
          <CheckboxInput
            label="I accept this blind spot"
            value={entry.accepted}
            isDisabled={!entry.note.trim()}
            disabledMessage="Write the reason first."
            onChange={(accepted) => {
              set({ accepted })
              if (accepted) onAccepted?.()
            }}
          />
        </>
      ) : (
        <Text type="supporting">Resolved by an approved decision above; nothing to accept unless that changes.</Text>
      )}
    </VStack>
  )
}

function AssumptionRegister({ props }: { props: ViewProps }) {
  const { spec, state } = props
  const rulingFor = (a: Assumption) => state.assumptions[a.id]?.ruling
  const [selectedId, setSelectedId] = useState<string | undefined>(
    () => spec.assumptions.find((a) => !assumptionRuled(state, a))?.id ?? spec.assumptions[0]?.id,
  )
  const selected = spec.assumptions.find((a) => a.id === selectedId) ?? spec.assumptions[0]
  if (!selected) return <Text type="supporting">The spec lists no assumptions.</Text>
  const entries = spec.assumptions.map((a) => {
    const ruling = rulingFor(a)
    return {
      id: a.id,
      label: `${a.id} · ${CERTAINTY_LABEL[effectiveCertainty(state, a)]}`,
      description: a.claim,
      isDone: assumptionRuled(state, a),
      status: ruling ? (
        <Token size="sm" color={RULING_COLOR[ruling]} label={RULINGS.find((r) => r.value === ruling)?.label ?? ruling} />
      ) : (
        <Token size="sm" color="blue" label="To rule" />
      ),
    }
  })
  const selectNext = () => {
    const nextId = nextOpenEntryId(entries, selected.id)
    if (nextId) setSelectedId(nextId)
  }
  return (
    <ListDetailRegister
      intro="Each one is something the spec depends on. Confirmed means it was checked on this machine; assumed means it was reasoned from code or transcripts but never seen happening; unverified means nobody has checked yet."
      doneLabel="ruled"
      listLabel="Assumptions"
      nextLabel="Next to rule"
      entries={entries}
      selectedId={selected.id}
      onSelect={setSelectedId}
      detail={<AssumptionDetail assumption={selected} props={props} onRuled={selectNext} />}
    />
  )
}

function BlindSpotRegister({ props }: { props: ViewProps }) {
  const { spec, state } = props
  const sets = blindSpotSets(spec, state)
  const isOpen = (b: BlindSpot) => ['open', 'reason-written'].includes(blindSpotStatus(b, spec, state, sets))
  const [selectedId, setSelectedId] = useState<string | undefined>(
    () => spec.blindSpots.find(isOpen)?.id ?? spec.blindSpots[0]?.id,
  )
  const selected = spec.blindSpots.find((b) => b.id === selectedId) ?? spec.blindSpots[0]
  if (!selected) return <Text type="supporting">The spec lists no blind spots.</Text>
  const entries = spec.blindSpots.map((b) => {
    const status = blindSpotStatus(b, spec, state, sets)
    return {
      id: b.id,
      label: `${b.id} · caused by ${b.sources.join(', ')}`,
      description: b.title,
      isDone: !isOpen(b),
      status: <BlindSpotStatusToken status={status} />,
    }
  })
  const selectNext = () => {
    const nextId = nextOpenEntryId(entries, selected.id)
    if (nextId) setSelectedId(nextId)
  }
  return (
    <ListDetailRegister
      intro="Cases where the spec's behavior might surprise someone. Settle each active blind spot by accepting it in a sentence of your own about why it is tolerable, or by asking Claude to research it; an approved scenario or constraint that resolves it needs neither."
      doneLabel="resolved"
      listLabel="Blind spots"
      nextLabel="Next to accept"
      entries={entries}
      selectedId={selected.id}
      onSelect={setSelectedId}
      detail={<BlindSpotDetail spot={selected} props={props} onAccepted={selectNext} />}
    />
  )
}

function AssumptionsTable({ spec }: { spec: LogicSpec }) {
  const openItem = useOpenItem()
  const columns: TableColumn<AssumptionRow>[] = [
    { key: 'id', header: 'ID', width: pixel(100), renderCell: (a) => <Text type="label">{a.id}</Text> },
    { key: 'claim', header: 'Assumption', width: proportional(4), renderCell: (a) => <Link onClick={() => openItem?.(a.id)}>{a.claim}</Link> },
    {
      key: 'certainty',
      header: 'Certainty',
      width: pixel(150),
      renderCell: (a) => (
        <VStack gap={1}>
          <HStack><CertaintyToken certainty={a.certainty} /></HStack>
          {a.originalCertainty ? <Text type="supporting">{`You set this; Claude said ${CERTAINTY_LABEL[a.originalCertainty]}`}</Text> : null}
        </VStack>
      ),
    },
    {
      key: 'ruling',
      header: 'Your ruling',
      width: pixel(170),
      renderCell: (a) => (a.ruling
        ? <Token size="sm" color={RULING_COLOR[a.ruling]} label={RULINGS.find((r) => r.value === a.ruling)?.label ?? a.ruling} />
        : <Text type="supporting">Not ruled on</Text>),
    },
    { key: 'note', header: 'Your note', width: proportional(3), renderCell: (a) => <Text type="supporting">{a.rulingNote ?? ''}</Text> },
  ]
  if (!spec.assumptions.length) return <Text type="supporting">The spec lists no assumptions.</Text>
  return <Table data={spec.assumptions} columns={columns} idKey="id" verticalAlign="top" dividers="rows" hasHover />
}

function BlindSpotsTable({ props }: { props: ViewProps }) {
  const { spec, state } = props
  const openItem = useOpenItem()
  const sets = blindSpotSets(spec, state)
  const columns: TableColumn<BlindSpotRow>[] = [
    { key: 'id', header: 'ID', width: pixel(100), renderCell: (b) => <Text type="label">{b.id}</Text> },
    { key: 'title', header: 'Blind spot', width: proportional(3), renderCell: (b) => <Link onClick={() => openItem?.(b.id)}>{b.title}</Link> },
    {
      key: 'sources',
      header: 'Caused by',
      width: proportional(2),
      renderCell: (b) => (b.sources.length
        ? <HStack gap={1} wrap="wrap">{b.sources.map((id) => <Text key={id}><ItemRef id={id} /></Text>)}</HStack>
        : <Text type="supporting">Nothing in particular</Text>),
    },
    {
      key: 'status',
      header: 'Status',
      width: pixel(130),
      renderCell: (b) => <BlindSpotStatusToken status={blindSpotStatus(b, spec, state, sets)} />,
    },
    { key: 'acceptance', header: 'Your acceptance', width: proportional(3), renderCell: (b) => <Text type="supporting">{b.acceptance ?? ''}</Text> },
  ]
  if (!spec.blindSpots.length) return <Text type="supporting">The spec lists no blind spots.</Text>
  return <Table data={spec.blindSpots} columns={columns} idKey="id" verticalAlign="top" dividers="rows" hasHover />
}

/** Assumptions and blind spots: rule on every assumption and accept or research every active blind spot in stage 1; stage 2 lists the folded outcomes as tables. */
export function RisksView(props: ViewProps) {
  const isStage2 = props.spec.stage === 2
  return (
    <VStack gap={6}>
      <VStack gap={3}>
        <Heading level={2}>Assumptions the spec stands on</Heading>
        {isStage2 ? <AssumptionsTable spec={props.spec} /> : <AssumptionRegister props={props} />}
      </VStack>
      <VStack gap={3}>
        <Heading level={2}>Blind spots you would be accepting</Heading>
        {isStage2 ? <BlindSpotsTable props={props} /> : <BlindSpotRegister props={props} />}
      </VStack>
    </VStack>
  )
}
