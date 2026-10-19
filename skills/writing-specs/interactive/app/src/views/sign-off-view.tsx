import { useRef, useState } from 'react'
import { Banner } from '@astryxdesign/core/Banner'
import { Button } from '@astryxdesign/core/Button'
import { CodeBlock } from '@astryxdesign/core/CodeBlock'
import { Collapsible } from '@astryxdesign/core/Collapsible'
import { Heading } from '@astryxdesign/core/Heading'
import { Card, HStack, VStack } from '@astryxdesign/core/Layout'
import { List, ListItem } from '@astryxdesign/core/List'
import { RadioList, RadioListItem } from '@astryxdesign/core/RadioList'
import { StatusDot } from '@astryxdesign/core/StatusDot'
import { Text } from '@astryxdesign/core/Text'
import { TextArea } from '@astryxdesign/core/TextArea'
import { decisionRecord, localStamp } from '../review-state'
import type { Export, LogicSpec, LogicSpecPayload, ReviewState } from '../spec-types'
import type { ReviewGate } from '../review-state'
import type { ViewProps } from './view-props'

export type SignOffProps = ViewProps & {
  gates: ReviewGate[]
  createExport: () => Export
  onExport: (data: Export) => void
  importStatus: string | null
  onImport: (file: File) => void
  /** Renders only the folded signed spec, with no review state, gates, sign, verdict, export or import controls; used while stage 3 is open. */
  readOnly?: boolean
}

const STAGE_HEADING: Record<1 | 2, string> = {
  1: 'Sign off stage 1 — what should happen',
  2: 'Sign off stage 2 — what to build',
}


/** The approval gate: every review gate must pass and the verdict must be approve before signing; any later edit clears the signature. With `readOnly`, only the folded signed spec shows. */
export function SignOffView(props: SignOffProps) {
  return props.readOnly ? <SignedSpecRecord payload={props.payload} spec={props.spec} /> : <ReviewSignOff {...props} />
}

type SignedRecordProps = { payload: LogicSpecPayload; spec: LogicSpec }

/** The signed record as the folded spec carries it. It never reads browser review state, so a fresh browser shows the same record as the reviewer who signed. */
function SignedSpecRecord({ payload, spec }: SignedRecordProps) {
  const signedAt = spec.signoff?.signedAt
  const signedRender = spec.signoff?.renderId ?? payload.renderId
  const scenarios = spec.scenarios.map((scenario) => ({
    id: scenario.id,
    outcome: scenario.dropReason ? 'dropped' : 'approved',
    dropReason: scenario.dropReason ?? null,
  }))
  const constraints = spec.constraints.map((constraint) => ({
    id: constraint.id,
    ruling: constraint.ruling ?? null,
    rejectReason: constraint.rejectReason ?? null,
  }))
  const placements = spec.requirements.map((requirement) => ({
    id: requirement.id,
    placement: requirement.scope === 'out' ? 'out' : requirement.condition ? 'conditional' : 'in',
    condition: requirement.condition ?? null,
  }))
  const record = {
    stage: spec.stage,
    status: spec.status,
    signedAt: signedAt ?? null,
    renderId: signedRender,
    scenarios,
    constraints,
    placements,
  }
  const approvedCount = scenarios.filter((item) => item.outcome === 'approved').length
  const summary = [
    { id: 'scenarios', label: 'Scenarios approved', value: `${approvedCount} of ${scenarios.length}` },
    { id: 'dropped', label: 'Scenarios dropped', value: String(scenarios.length - approvedCount) },
    { id: 'constraints', label: 'Constraints approved or rewritten', value: `${constraints.filter((item) => item.ruling === 'approved' || item.ruling === 'rewritten').length} of ${constraints.length}` },
    { id: 'placements', label: 'Requirements in scope', value: `${placements.filter((item) => item.placement !== 'out').length} of ${placements.length}` },
  ]
  return (
    <VStack gap={4}>
      <VStack gap={2}>
        <Heading level={2}>{STAGE_HEADING[spec.stage]}</Heading>
        <Text type="supporting" as="p">This spec is signed. The record below is read-only while stage 3 is open.</Text>
      </VStack>
      <Card>
        <VStack gap={2}>
          <Banner
            status="success"
            title={signedAt ? `Signed ${new Date(signedAt).toLocaleString()}` : 'Signed'}
            description={`Render ${signedRender}`}
            collapsible={false}
          />
          <Text type="label">{`Status: ${spec.status}`}</Text>
        </VStack>
      </Card>
      <Card padding={0}>
        <List hasDividers>
          {summary.map((item) => (
            <ListItem
              key={item.id}
              label={item.label}
              endContent={<Text type="supporting" hasTabularNumbers>{item.value}</Text>}
            />
          ))}
        </List>
      </Card>
      <VStack gap={2}>
        <Heading level={3}>Decision record</Heading>
        <Collapsible trigger="Show the record as JSON" defaultIsOpen={false}>
          <CodeBlock language="json" code={JSON.stringify(record, null, 2)} maxHeight={480} width="100%" hasCopyButton={false} />
        </Collapsible>
      </VStack>
    </VStack>
  )
}

function ReviewSignOff({ payload, spec, state, update, gates, createExport, onExport, importStatus, onImport }: SignOffProps) {
  const [copyStatus, setCopyStatus] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)
  const allPassed = gates.every((gate) => gate.done >= gate.total)
  const record = decisionRecord(state, spec)
  const recordJson = JSON.stringify(record, null, 2)

  const download = () => {
    const data = createExport()
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${payload.slug}-decisions-${localStamp(new Date())}.json`
    anchor.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 0)
    onExport(data)
    setCopyStatus('Decision export downloaded. Claude moves it next to review.html when it picks it up.')
  }
  const copy = async () => {
    const data = createExport()
    try {
      if (!navigator.clipboard?.writeText) throw new Error('Clipboard unavailable')
      await navigator.clipboard.writeText(JSON.stringify(data, null, 2))
      onExport(data)
      setCopyStatus('Decision export copied.')
    } catch {
      setCopyStatus('Copy is blocked here — use Download')
    }
  }

  const disabledReason = !allPassed ? 'Signing is disabled until every gate is complete.' : state.verdict !== 'approve' ? 'Choose approve to enable signing.' : null

  return (
    <VStack gap={4}>
      <VStack gap={2}>
        <Heading level={2}>{STAGE_HEADING[spec.stage]}</Heading>
        <Text type="supporting" as="p">
          Signing is the approval gate. Every gate below must pass, and the verdict must be approve. Any later edit clears the signature.
        </Text>
      </VStack>
      <Card padding={0}>
        <List hasDividers>
          {gates.map((gate) => (
            <ListItem
              key={gate.id}
              label={gate.label}
              startContent={<StatusDot variant={gate.done >= gate.total ? 'success' : 'warning'} label={gate.done >= gate.total ? 'Done' : 'Open'} />}
              endContent={
                <Text type="supporting" hasTabularNumbers>
                  {gate.total === 0 ? 'None needed' : `${gate.done} / ${gate.total}`}
                </Text>
              }
            />
          ))}
        </List>
      </Card>
      <Card>
          <VStack gap={3}>
            <RadioList label="Verdict" value={state.verdict ?? ''} onChange={(value) => update((current) => ({ ...current, verdict: value as ReviewState['verdict'] }))}>
              <RadioListItem value="approve" label="Approve" description="The spec is ready to build as reviewed." />
              <RadioListItem value="send-back" label="Send back" description="Something needs another brainstorm pass. Say what in the note." />
            </RadioList>
            <TextArea
              label="Note to Claude"
              value={state.verdictNote}
              onChange={(verdictNote) => update((current) => ({ ...current, verdictNote }))}
              isRequired={state.verdict === 'send-back'}
              rows={3}
            />
            <HStack gap={2} wrap="wrap" align="center">
              <Button
                variant="primary"
                label={state.signedAt ? 'Signed' : 'Record sign-off'}
                isDisabled={!allPassed || state.verdict !== 'approve' || Boolean(state.signedAt)}
                onClick={() => update((current) => ({ ...current, signedAt: new Date().toISOString() }))}
              />
              {disabledReason ? <Text type="supporting">{disabledReason}</Text> : null}
            </HStack>
            {state.signedAt ? (
              <Banner status="success" title={`Signed ${new Date(state.signedAt).toLocaleString()}`} description={`Render ${payload.renderId}`} collapsible={false} />
            ) : null}
          </VStack>
        </Card>
      <VStack gap={2}>
        <Heading level={3}>Decision record</Heading>
        <Collapsible trigger="Show the record as JSON" defaultIsOpen={false}>
          <CodeBlock language="json" code={recordJson} maxHeight={480} width="100%" hasCopyButton={false} />
        </Collapsible>
        <HStack gap={2} wrap="wrap">
          <Button label="Download" onClick={download} />
          <Button label="Copy" onClick={() => void copy()} />
          <Button label="Import" onClick={() => fileInputRef.current?.click()} />
          <input
            ref={fileInputRef}
            type="file"
            accept="application/json,.json"
            hidden
            onChange={(event) => {
              const file = event.currentTarget.files?.[0]
              if (file) onImport(file)
              event.currentTarget.value = ''
            }}
          />
        </HStack>
        {copyStatus ? <Text type="supporting">{copyStatus}</Text> : null}
        {importStatus ? <Text type="supporting">{importStatus}</Text> : null}
      </VStack>
    </VStack>
  )
}
