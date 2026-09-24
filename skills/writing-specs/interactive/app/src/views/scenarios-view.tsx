import { useState, type ReactNode } from 'react'
import { Button } from '@astryxdesign/core/Button'
import { CheckboxInput } from '@astryxdesign/core/CheckboxInput'
import { Dialog, DialogHeader } from '@astryxdesign/core/Dialog'
import { EmptyState } from '@astryxdesign/core/EmptyState'
import { Heading } from '@astryxdesign/core/Heading'
import { HStack, VStack } from '@astryxdesign/core/Layout'
import { Selector } from '@astryxdesign/core/Selector'
import { Table, TableCell, pixel, proportional, type TableColumn, type TablePlugin } from '@astryxdesign/core/Table'
import { Text } from '@astryxdesign/core/Text'
import { TextArea } from '@astryxdesign/core/TextArea'
import { TextInput } from '@astryxdesign/core/TextInput'
import { Token } from '@astryxdesign/core/Token'
import type { Scenario, ScenarioOutcome, ScenarioRequest } from '../spec-types'
import { pendingScenarioRequests, requestId, scenarioThen, type Update } from '../review-state'
import { ChangedToken, ClaudeWroteToken, SpecMarkdown } from './shared'
import type { ViewProps } from './view-props'

type Row = { kind: 'scenario'; id: string; scenario: Scenario } | { kind: 'request'; id: string; request: ScenarioRequest }

// Selector options render as plain text, so strip markdown backticks the spec might use in a `then` clause.
const plain = (text: string) => text.replace(/`/g, '')

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

function scenarioColumns(props: ViewProps): TableColumn<Row>[] {
  const { state, update, changedIds } = props
  const cell = (render: (s: Scenario) => ReactNode) => (row: Row) => (row.kind === 'scenario' ? render(row.scenario) : null)
  return [
    {
      key: 'approved',
      header: 'Approved',
      width: pixel(104),
      renderCell: cell((s) => (
        <CheckboxInput
          label={`Approve ${s.id}`}
          isLabelHidden
          value={Boolean(state.scenarioApproved[s.id])}
          isDisabled={state.scenarioOutcomes[s.id]?.choice === 'custom' && !state.scenarioOutcomes[s.id]?.custom.trim()}
          disabledMessage="Write your outcome first."
          onChange={(approved) => update((st) => ({ ...st, scenarioApproved: { ...st.scenarioApproved, [s.id]: approved } }), s.id)}
        />
      )),
    },
    {
      key: 'id',
      header: 'Scenario',
      width: pixel(96),
      renderCell: cell((s) => (
        <VStack gap={1}>
          <Text type="label">{s.id}</Text>
          {s.requestId ? <HStack><Token size="sm" label="Requested" description="You asked for this scenario." /></HStack> : null}
          <HStack><ChangedToken id={s.id} changedIds={changedIds} short /></HStack>
        </VStack>
      )),
    },
    { key: 'given', header: 'Given', width: proportional(2), renderCell: cell((s) => <Clause keyword="Given" text={s.given} />) },
    { key: 'when', header: 'When', width: proportional(2), renderCell: cell((s) => <Clause keyword="When" text={s.when} />) },
    { key: 'then', header: 'Then', width: proportional(2.6), renderCell: cell((s) => <OutcomeCell s={s} props={props} />) },
    {
      key: 'why',
      header: 'Why',
      width: proportional(2),
      renderCell: cell((s) => (
        <VStack gap={1}>
          <HStack><ClaudeWroteToken /></HStack>
          <SpecMarkdown compact>{`${s.explanation}${s.refs.length ? ` (${s.refs.join(', ')})` : ''}`}</SpecMarkdown>
        </VStack>
      )),
    },
  ]
}

function requestRowPlugin(update: Update, columnCount: number): TablePlugin<Row> {
  return {
    transformBodyRow: (rowProps, row) =>
      row.kind === 'request'
        ? {
            ...rowProps,
            children: (
              <TableCell colSpan={columnCount}>
                <RequestRow request={row.request} update={update} />
              </TableCell>
            ),
          }
        : rowProps,
  }
}

function AskDialog({ isOpen, onClose, update }: { isOpen: boolean; onClose: () => void; update: Update }) {
  const [draft, setDraft] = useState('')
  const close = () => {
    setDraft('')
    onClose()
  }
  const submit = () => {
    const text = draft.trim()
    if (!text) return
    update((st) => ({ ...st, scenarioRequests: [...st.scenarioRequests, { id: requestId('scenario'), text, requestedAt: new Date().toISOString() }] }))
    close()
  }
  if (!isOpen) return null
  return (
    <Dialog isOpen onOpenChange={(open) => !open && close()} width={640} purpose="form">
      <DialogHeader title="Ask for another scenario" subtitle="Claude turns it into Given / When / Then" onOpenChange={(open) => !open && close()} />
      <VStack gap={3} padding={4}>
        <Text type="supporting">
          Describe a situation in your own words. It shows in the approval table as waiting for Claude until Claude converts it into a scenario in the spec.
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

/** Every Given/When/Then scenario, split into an approval table and an approved table; supports Claude's alternative outcomes and new scenario requests. */
export function ScenariosView(props: ViewProps) {
  const { spec, state, update } = props
  const [isAsking, setIsAsking] = useState(false)
  const toRow = (scenario: Scenario): Row => ({ kind: 'scenario', id: scenario.id, scenario })
  const awaiting: Row[] = [
    ...spec.scenarios.filter((s) => !state.scenarioApproved[s.id]).map(toRow),
    ...pendingScenarioRequests(state, spec).map((request): Row => ({ kind: 'request', id: request.id, request })),
  ]
  const approved = spec.scenarios.filter((s) => state.scenarioApproved[s.id]).map(toRow)
  const columns = scenarioColumns(props)
  const plugins = { requestRows: requestRowPlugin(update, columns.length) }

  return (
    <VStack gap={6}>
      <VStack gap={2}>
        <Heading level={2}>Scenarios</Heading>
        <Text type="supporting" as="p">
          What the spec does in specific situations. Approve each one, or pick a different outcome from Claude's alternatives or write your own; a different
          outcome goes into the decision record as a change to the spec. Approved scenarios move to the table below.
        </Text>
      </VStack>

      <VStack gap={2}>
        <HStack gap={2} align="center">
          <Heading level={3}>Awaiting approval</Heading>
          <Text type="supporting" hasTabularNumbers>{awaiting.length}</Text>
        </HStack>
        <Table
          data={awaiting}
          columns={columns}
          plugins={plugins}
          idKey="id"
          verticalAlign="top"
          dividers="rows"
          emptyState={<EmptyState title="Every scenario is approved" isCompact />}
        />
        <Button variant="secondary" width="100%" icon={<span aria-hidden>+</span>} label="Ask for another scenario" onClick={() => setIsAsking(true)} />
      </VStack>

      <VStack gap={2}>
        <HStack gap={2} align="center">
          <Heading level={3}>Approved</Heading>
          <Text type="supporting" hasTabularNumbers>{approved.length}</Text>
        </HStack>
        <Table
          data={approved}
          columns={columns}
          idKey="id"
          verticalAlign="top"
          dividers="rows"
          emptyState={<EmptyState title="Nothing approved yet" isCompact />}
        />
      </VStack>

      <AskDialog isOpen={isAsking} onClose={() => setIsAsking(false)} update={update} />
    </VStack>
  )
}
