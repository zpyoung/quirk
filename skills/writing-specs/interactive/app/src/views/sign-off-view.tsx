import { useRef, useState } from 'react'
import { Banner } from '@astryxdesign/core/Banner'
import { Button } from '@astryxdesign/core/Button'
import { CodeBlock } from '@astryxdesign/core/CodeBlock'
import { Heading } from '@astryxdesign/core/Heading'
import { Card, HStack, VStack } from '@astryxdesign/core/Layout'
import { List, ListItem } from '@astryxdesign/core/List'
import { RadioList, RadioListItem } from '@astryxdesign/core/RadioList'
import { StatusDot } from '@astryxdesign/core/StatusDot'
import { Text } from '@astryxdesign/core/Text'
import { TextArea } from '@astryxdesign/core/TextArea'
import { decisionRecord, localStamp } from '../review-state'
import type { Export, ReviewState } from '../spec-types'
import type { ReviewGate } from '../review-state'
import type { ViewProps } from './view-props'

export type SignOffProps = ViewProps & {
  gates: ReviewGate[]
  createExport: () => Export
  onExport: (data: Export) => void
  importStatus: string | null
  onImport: (file: File) => void
}

const STAGE_HEADING: Record<1 | 2, string> = {
  1: 'Sign off stage 1 — what should happen',
  2: 'Sign off stage 2 — what to build',
}

/** The approval gate: every review gate must pass and the verdict must be approve before signing; any later edit clears the signature. */
export function SignOffView({ payload, spec, state, update, gates, createExport, onExport, importStatus, onImport }: SignOffProps) {
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
    setCopyStatus('Decision export downloaded.')
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
        <CodeBlock language="json" code={recordJson} maxHeight={480} width="100%" />
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
