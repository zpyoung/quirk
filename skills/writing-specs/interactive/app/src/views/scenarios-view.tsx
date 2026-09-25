import { useMemo, useState } from 'react'
import { Button } from '@astryxdesign/core/Button'
import { Dialog, DialogHeader } from '@astryxdesign/core/Dialog'
import { Heading } from '@astryxdesign/core/Heading'
import { HStack, VStack } from '@astryxdesign/core/Layout'
import { SegmentedControl, SegmentedControlItem } from '@astryxdesign/core/SegmentedControl'
import { Selector, SelectorOption } from '@astryxdesign/core/Selector'
import { Table, pixel, proportional, type TableColumn } from '@astryxdesign/core/Table'
import { Text } from '@astryxdesign/core/Text'
import { TextArea } from '@astryxdesign/core/TextArea'
import { TextInput } from '@astryxdesign/core/TextInput'
import { Token } from '@astryxdesign/core/Token'
import type { Behavior, Scenario, ScenarioOutcome, ScenarioRequest, ReviewState } from '../spec-types'
import { pendingScenarioRequests, requestId, scenarioThen, type Update } from '../review-state'
import { ChangedRowLabel, changedRowsPlugin, ClaudeAddedToken, SpecMarkdown } from './shared'
import type { ViewProps } from './view-props'

// Selector options render as plain text, so strip markdown backticks the spec might use in a `then` clause.
const plain = (text: string) => text.replace(/`/g, '')

// A homomorphic copy of Scenario's shape, plain enough to satisfy Table's `Record<string, unknown>` row constraint.
type ScenarioRow = { [K in keyof Scenario]: Scenario[K] }

function hasScenarioEntry(state: ReviewState, id: string): boolean {
  return Object.hasOwn(state.scenarioApproved, id) || Object.hasOwn(state.scenarioDrops, id) || Object.hasOwn(state.scenarioUpdates, id)
}

function Clause({ keyword, text }: { keyword: string; text: string }) {
  return <SpecMarkdown compact>{`**${keyword}** ${text}`}</SpecMarkdown>
}

function ThenLabel({ label }: { label: string }) {
  if (!label.startsWith('Then ')) return <>{label}</>
  return <><strong>Then</strong>{label.slice(4)}</>
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
        renderValue={(option) => <Text><ThenLabel label={option.label ?? option.value} /></Text>}
        renderOption={(option) => (
          <SelectorOption label={<ThenLabel label={option.label ?? option.value} />} description={option.description} />
        )}
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

type Decision = 'approve' | 'update' | 'drop'

function DecisionCell({ s, props }: { s: Scenario; props: ViewProps }) {
  const { state, update } = props
  // drop and update entries exist as soon as they are picked, so blank text keeps the choice without resolving the scenario
  const isDropped = Object.hasOwn(state.scenarioDrops, s.id)
  const isUpdating = Object.hasOwn(state.scenarioUpdates, s.id)
  const value: Decision | '' = isDropped ? 'drop' : isUpdating ? 'update' : state.scenarioApproved[s.id] ? 'approve' : ''
  const outcome = state.scenarioOutcomes[s.id]
  const isOutcomeMissing = outcome?.choice === 'custom' && !outcome.custom.trim()
  const decide = (decision: Decision) =>
    update((st) => {
      const scenarioDrops = { ...st.scenarioDrops }
      const scenarioUpdates = { ...st.scenarioUpdates }
      const scenarioApproved = { ...st.scenarioApproved }
      delete scenarioDrops[s.id]
      delete scenarioUpdates[s.id]
      delete scenarioApproved[s.id]
      if (decision === 'drop') scenarioDrops[s.id] = st.scenarioDrops[s.id] ?? ''
      else if (decision === 'update') scenarioUpdates[s.id] = st.scenarioUpdates[s.id] ?? ''
      else scenarioApproved[s.id] = true
      return { ...st, scenarioDrops, scenarioUpdates, scenarioApproved }
    }, s.id)
  return (
    <VStack gap={1.5}>
      <SegmentedControl size="sm" layout="fill" label={`Decision for ${s.id}`} value={value} onChange={(next) => decide(next as Decision)}>
        <SegmentedControlItem value="approve" label="Approve" isDisabled={isOutcomeMissing} />
        <SegmentedControlItem value="update" label="Update" />
        <SegmentedControlItem value="drop" label="Drop" />
      </SegmentedControl>
      {isOutcomeMissing && value === '' ? <Text type="supporting">Write your outcome first.</Text> : null}
      {isUpdating ? (
        <TextArea
          label={`What should change in ${s.id}`}
          isLabelHidden
          rows={3}
          placeholder="What should change in this scenario?"
          value={state.scenarioUpdates[s.id]}
          onChange={(feedback) => update((st) => ({ ...st, scenarioUpdates: { ...st.scenarioUpdates, [s.id]: feedback } }), s.id)}
        />
      ) : null}
      {isUpdating && state.scenarioUpdates[s.id].trim() ? <HStack><Token size="sm" color="yellow" label="Waiting for Claude" description="Claude revises this scenario from your note; you decide it again after." /></HStack> : null}
      {isDropped ? (
        <TextArea
          label={`Reason for dropping ${s.id}`}
          isLabelHidden
          rows={2}
          placeholder="Why drop this scenario?"
          value={state.scenarioDrops[s.id]}
          onChange={(reason) => update((st) => ({ ...st, scenarioDrops: { ...st.scenarioDrops, [s.id]: reason } }), s.id)}
        />
      ) : null}
    </VStack>
  )
}

function scenarioColumns(props: ViewProps, isStage2: boolean): TableColumn<ScenarioRow>[] {
  const { state, changedIds } = props
  const columns: TableColumn<ScenarioRow>[] = [
    {
      key: 'decision',
      header: 'Decision',
      width: pixel(isStage2 ? 128 : 240),
      renderCell: (s) => {
        if (isStage2 && !s.reopened) {
          // folded stage-2 scenarios carry their final outcome directly; only a reopened scenario still tracks state
          const approved = !s.dropReason
          return <Token size="sm" color={approved ? 'green' : 'default'} label={approved ? 'Approved' : 'Dropped'} description={s.dropReason} />
        }
        return <DecisionCell s={s} props={props} />
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
          ) : s.provenance === 'claude' && (!isStage2 || !hasScenarioEntry(state, s.id)) ? (
            <HStack><ClaudeAddedToken /></HStack>
          ) : null}
          {s.requestId ? <HStack><Token size="sm" label="Requested" description="You asked for this scenario." /></HStack> : null}
          <ChangedRowLabel id={s.id} changedIds={changedIds} />
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
      header: 'Why (Claude wrote this)',
      width: proportional(2),
      renderCell: (s) => <SpecMarkdown compact>{s.explanation}</SpecMarkdown>,
    },
  ]
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
  const { spec, changedIds } = props
  const scenarios = spec.scenarios.filter((s) => s.behavior === behavior.id)
  const plugins = useMemo(() => ({ changed: changedRowsPlugin<ScenarioRow>(changedIds) }), [changedIds])
  const columns = scenarioColumns(props, spec.stage === 2)
  return (
    <VStack gap={2}>
      <VStack gap={0.5}>
        <HStack gap={2} align="center" wrap="wrap">
          <Heading level={3}>{behavior.rule}</Heading>
          <Text type="supporting" hasTabularNumbers>{scenarios.length}</Text>
        </HStack>
        {behavior.detail ? <SpecMarkdown compact>{behavior.detail}</SpecMarkdown> : null}
      </VStack>
      <Table data={scenarios} columns={columns} plugins={plugins} idKey="id" verticalAlign="top" dividers="rows" />
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
            ? "What the spec does in specific situations, grouped under the rule each illustrates. Approve each scenario (optionally with a different outcome), ask Claude to update it, or drop it with a reason."
            : 'Stage 1 is signed and shown here read-only. A reopened scenario needs re-approval; everything else is for reference.'}
        </Text>
      </VStack>
      {spec.behaviors.map((behavior) => <BehaviorGroup key={behavior.id} behavior={behavior} props={props} />)}
    </VStack>
  )
}
