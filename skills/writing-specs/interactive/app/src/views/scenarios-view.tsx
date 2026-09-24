import { useState } from 'react'
import { Button } from '@astryxdesign/core/Button'
import { CheckboxInput } from '@astryxdesign/core/CheckboxInput'
import { Dialog, DialogHeader } from '@astryxdesign/core/Dialog'
import { Heading } from '@astryxdesign/core/Heading'
import { HStack, VStack } from '@astryxdesign/core/Layout'
import { Selector } from '@astryxdesign/core/Selector'
import { Table, pixel, proportional, type TableColumn } from '@astryxdesign/core/Table'
import { Text } from '@astryxdesign/core/Text'
import { TextArea } from '@astryxdesign/core/TextArea'
import { TextInput } from '@astryxdesign/core/TextInput'
import { Token } from '@astryxdesign/core/Token'
import type { Behavior, Scenario, ScenarioOutcome, ScenarioRequest, ReviewState } from '../spec-types'
import { pendingScenarioRequests, requestId, scenarioThen, type Update } from '../review-state'
import { ChangedToken, ClaudeWroteToken, PreselectedToken, ProvenanceToken, SpecMarkdown } from './shared'
import type { ViewProps } from './view-props'

// Selector options render as plain text, so strip markdown backticks the spec might use in a `then` clause.
const plain = (text: string) => text.replace(/`/g, '')

// A homomorphic copy of Scenario's shape, plain enough to satisfy Table's `Record<string, unknown>` row constraint.
type ScenarioRow = { [K in keyof Scenario]: Scenario[K] }

function hasScenarioEntry(state: ReviewState, id: string): boolean {
  return Object.hasOwn(state.scenarioApproved, id) || Object.hasOwn(state.scenarioDrops, id)
}

function Clause({ keyword, text }: { keyword: string; text: string }) {
  return <SpecMarkdown compact>{`**${keyword}** ${text}`}</SpecMarkdown>
}

function OutcomeCell({ s, props }: { s: Scenario; props: ViewProps }) {
  const { state, update } = props
  const outcome = state.scenarioOutcomes[s.id] ?? { choice: 'spec' as const, custom: '' }
  const set = (patch: Partial<ScenarioOutcome>) =>
    update(
      (st) => ({
        ...st,
        scenarioOutcomes: { ...st.scenarioOutcomes, [s.id]: { ...outcome, ...patch } },
        // a different outcome is a different scenario, so an earlier approval no longer applies
        scenarioApproved: { ...st.scenarioApproved, [s.id]: false },
      }),
      s.id,
    )
  return (
    <VStack gap={1.5}>
      <Selector
        size="sm"
        label={`Outcome for ${s.id}`}
        isLabelHidden
        width="100%"
        value={outcome.choice}
        onChange={(value) => set({ choice: value as ScenarioOutcome['choice'] })}
        renderValue={(option) => <Text>{option.label}</Text>}
        options={[
          { value: 'spec', label: `Then ${plain(s.then)}`, description: "The spec's outcome" },
          ...s.alternatives.map((alt, i) => ({ value: `alt-${i}`, label: `Then ${plain(alt)}`, description: 'Suggested by Claude' })),
          { value: 'custom', label: 'Write my own…' },
        ]}
      />
      {outcome.choice === 'custom' ? (
        <TextInput size="sm" label="Then…" isLabelHidden placeholder="Then…" value={outcome.custom} onChange={(custom) => set({ custom })} />
      ) : null}
      {scenarioThen(state, s) !== s.then ? <Token size="sm" color="orange" label="Changes the spec" /> : null}
    </VStack>
  )
}

function DropCell({ s, update, dropReason }: { s: Scenario; update: Update; dropReason?: string }) {
  return (
    <TextArea
      label={`Reason for dropping ${s.id}`}
      isLabelHidden
      rows={2}
      placeholder="Drop this scenario — why?"
      value={dropReason ?? ''}
      onChange={(reason) =>
        update((st) => {
          const scenarioDrops = { ...st.scenarioDrops }
          const scenarioApproved = { ...st.scenarioApproved }
          if (reason.trim()) {
            scenarioDrops[s.id] = reason
            delete scenarioApproved[s.id]
          } else {
            delete scenarioDrops[s.id]
          }
          return { ...st, scenarioDrops, scenarioApproved }
        }, s.id)
      }
    />
  )
}

function scenarioColumns(props: ViewProps, isStage2: boolean): TableColumn<ScenarioRow>[] {
  const { state, update, changedIds } = props
  const columns: TableColumn<ScenarioRow>[] = [
    {
      key: 'approved',
      header: 'Approved',
      width: pixel(104),
      renderCell: (s) => {
        const editable = !isStage2 || Boolean(s.reopened)
        if (!editable) {
          // folded stage-2 scenarios carry their final outcome directly; only a reopened scenario still tracks state
          const approved = !s.dropReason
          return <Token size="sm" color={approved ? 'green' : 'default'} label={approved ? 'Approved' : 'Not approved'} />
        }
        const dropped = Boolean(state.scenarioDrops[s.id])
        return (
          <CheckboxInput
            label={`Approve ${s.id}`}
            isLabelHidden
            value={Boolean(state.scenarioApproved[s.id])}
            isDisabled={dropped || (state.scenarioOutcomes[s.id]?.choice === 'custom' && !state.scenarioOutcomes[s.id]?.custom.trim())}
            disabledMessage={dropped ? 'Dropped — clear the drop reason first.' : 'Write your outcome first.'}
            onChange={(approved) =>
              update((st) => {
                const scenarioDrops = { ...st.scenarioDrops }
                if (approved) delete scenarioDrops[s.id]
                return { ...st, scenarioApproved: { ...st.scenarioApproved, [s.id]: approved }, scenarioDrops }
              }, s.id)
            }
          />
        )
      },
    },
    {
      key: 'id',
      header: 'Scenario',
      width: pixel(160),
      renderCell: (s) => (
        <VStack gap={1}>
          <Text type="label">{s.id}</Text>
          {s.reopened ? (
            <HStack><Token size="sm" color="orange" label="Reopened" description={s.reopened.reason} /></HStack>
          ) : s.provenance === 'claude' && !hasScenarioEntry(state, s.id) ? (
            <HStack gap={1} wrap="wrap"><ProvenanceToken item={s} /><PreselectedToken /></HStack>
          ) : !isStage2 ? (
            <HStack><ProvenanceToken item={s} /></HStack>
          ) : null}
          {s.requestId ? <HStack><Token size="sm" label="Requested" description="You asked for this scenario." /></HStack> : null}
          {s.extraReason ? <HStack><Token size="sm" color="yellow" label="Extra example" description={s.extraReason} /></HStack> : null}
          <HStack><ChangedToken id={s.id} changedIds={changedIds} short /></HStack>
        </VStack>
      ),
    },
    { key: 'given', header: 'Given', width: proportional(2), renderCell: (s) => <Clause keyword="Given" text={s.given} /> },
    { key: 'when', header: 'When', width: proportional(2), renderCell: (s) => <Clause keyword="When" text={s.when} /> },
    {
      key: 'then',
      header: 'Then',
      width: proportional(2.6),
      renderCell: (s) => (!isStage2 ? <OutcomeCell s={s} props={props} /> : <Clause keyword="Then" text={scenarioThen(state, s)} />),
    },
    {
      key: 'why',
      header: 'Why',
      width: proportional(2),
      renderCell: (s) => (
        <VStack gap={1}>
          <HStack><ClaudeWroteToken /></HStack>
          <SpecMarkdown compact>{s.explanation}</SpecMarkdown>
        </VStack>
      ),
    },
  ]
  if (!isStage2) {
    columns.push({
      key: 'drop',
      header: 'Drop',
      width: pixel(200),
      renderCell: (s) => <DropCell s={s} update={update} dropReason={state.scenarioDrops[s.id]} />,
    })
  }
  return columns
}

function RequestRow({ request, update }: { request: ScenarioRequest; update: Update }) {
  return (
    <HStack gap={3} align="start">
      <Token size="sm" color="yellow" label="Waiting for Claude" />
      <Text>{request.text}</Text>
      <Button
        size="sm"
        variant="ghost"
        label="Withdraw"
        onClick={() => update((st) => ({ ...st, scenarioRequests: st.scenarioRequests.filter((x) => x.id !== request.id) }))}
      />
    </HStack>
  )
}

function AskDialog({ isOpen, onClose, behavior, update }: { isOpen: boolean; onClose: () => void; behavior: Behavior; update: Update }) {
  const [draft, setDraft] = useState('')
  const close = () => {
    setDraft('')
    onClose()
  }
  const submit = () => {
    const text = draft.trim()
    if (!text) return
    update((st) => ({ ...st, scenarioRequests: [...st.scenarioRequests, { id: requestId('scenario'), behavior: behavior.id, text, requestedAt: new Date().toISOString() }] }))
    close()
  }
  if (!isOpen) return null
  return (
    <Dialog isOpen onOpenChange={(open) => !open && close()} width={640} purpose="form">
      <DialogHeader title={`Ask for another scenario under ${behavior.rule}`} subtitle="Claude turns it into Given / When / Then" onOpenChange={(open) => !open && close()} />
      <VStack gap={3} padding={4}>
        <Text type="supporting">
          Describe a situation in your own words. It shows here as waiting for Claude until Claude converts it into a scenario under this behavior.
        </Text>
        <TextArea label="Scenario" rows={4} value={draft} onChange={setDraft} placeholder="e.g. What happens if the input is empty?" />
        <HStack gap={2} justify="end">
          <Button variant="secondary" label="Cancel" onClick={close} />
          <Button variant="primary" label="Send to Claude" isDisabled={!draft.trim()} onClick={submit} />
        </HStack>
      </VStack>
    </Dialog>
  )
}

function BehaviorRequests({ behavior, props }: { behavior: Behavior; props: ViewProps }) {
  const { spec, state, update } = props
  const [isAsking, setIsAsking] = useState(false)
  const pending = pendingScenarioRequests(state, spec).filter((request) => request.behavior === behavior.id)
  return (
    <VStack gap={2}>
      {pending.map((request) => <RequestRow key={request.id} request={request} update={update} />)}
      <Button variant="secondary" width="100%" icon={<span aria-hidden>+</span>} label="Ask for another scenario" onClick={() => setIsAsking(true)} />
      <AskDialog isOpen={isAsking} onClose={() => setIsAsking(false)} behavior={behavior} update={update} />
    </VStack>
  )
}

function BehaviorGroup({ behavior, props }: { behavior: Behavior; props: ViewProps }) {
  const { spec } = props
  const scenarios = spec.scenarios.filter((s) => s.behavior === behavior.id)
  const isOverLimit = scenarios.length > 3
  const columns = scenarioColumns(props, spec.stage === 2)
  return (
    <VStack gap={2}>
      <VStack gap={0.5}>
        <HStack gap={2} align="center" wrap="wrap">
          <Heading level={3}>{behavior.rule}</Heading>
          <Text type="supporting" hasTabularNumbers>{scenarios.length}</Text>
          {isOverLimit ? <Token size="sm" color="orange" label="More than 3 key examples" /> : null}
        </HStack>
        {behavior.detail ? <SpecMarkdown compact>{behavior.detail}</SpecMarkdown> : null}
      </VStack>
      <Table data={scenarios} columns={columns} idKey="id" verticalAlign="top" dividers="rows" />
      {spec.stage === 1 ? <BehaviorRequests behavior={behavior} props={props} /> : null}
    </VStack>
  )
}

/** Scenarios grouped under the behavior rule each illustrates; stage 1 is fully editable, stage 2 is read-only except reopened scenarios. */
export function ScenariosView(props: ViewProps) {
  const { spec } = props
  return (
    <VStack gap={6}>
      <VStack gap={2}>
        <Heading level={2}>Behaviors & scenarios</Heading>
        <Text type="supporting" as="p">
          {spec.stage === 1
            ? "What the spec does in specific situations, grouped under the rule each illustrates. Approve each scenario, pick a different outcome, or drop it with a reason."
            : 'Stage 1 is signed and shown here read-only. A reopened scenario needs re-approval; everything else is for reference.'}
        </Text>
      </VStack>
      {spec.behaviors.map((behavior) => <BehaviorGroup key={behavior.id} behavior={behavior} props={props} />)}
    </VStack>
  )
}
