import { useState, type ReactNode } from 'react'
import { Card, HStack, VStack } from '@astryxdesign/core/Layout'
import { Collapsible } from '@astryxdesign/core/Collapsible'
import { Heading } from '@astryxdesign/core/Heading'
import { Markdown, type MarkdownComponents } from '@astryxdesign/core/Markdown'
import { SegmentedControl, SegmentedControlItem } from '@astryxdesign/core/SegmentedControl'
import { Table, proportional, type TableColumn } from '@astryxdesign/core/Table'
import { Text } from '@astryxdesign/core/Text'
import { Token } from '@astryxdesign/core/Token'
import type { Approach, Comparison, CompareViewProps } from '../../compare-types'
import { OFFLINE_MARKDOWN_COMPONENTS } from '../shared'
import { ProcessFlow } from './diagrams/process-flow'
import { SchemaDiagram } from './diagrams/schema-diagram'
import { SequenceDiagram } from './diagrams/sequence-diagram'

const ABSOLUTE_URL = /^[a-z][a-z0-9+.-]*:/i

/** Offline-safe markdown for an embedded spec: its relative links point at files this page doesn't have, so they read as plain text. */
const SPEC_MARKDOWN_COMPONENTS: MarkdownComponents = {
  ...OFFLINE_MARKDOWN_COMPONENTS,
  link: ({ href, children }) =>
    ABSOLUTE_URL.test(href) ? <a href={href} target="_blank" rel="noopener noreferrer">{children}</a> : <span>{children}</span>,
}

const DEPLOY_LABEL = { stated: 'Stated in the spec', implied: 'Implied by the spec', 'not-stated': 'Not stated' } as const

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <VStack gap={1}>
      <Heading level={3}>{title}</Heading>
      {children}
    </VStack>
  )
}

const NotProvided = () => <Text type="supporting">not provided</Text>

type TraceRow = { id: string; stage: string; trace: string }

function WorkedExample({ approach, example }: { approach: Approach; example: Comparison['example'] }) {
  const trace = approach.exampleTrace
  if (!example || !trace || trace.length === 0) return <NotProvided />
  const rows: TraceRow[] = example.stages.map((stage, index) => ({ id: `stage-${index}`, stage, trace: trace[index] ?? '' }))
  const columns: TableColumn<TraceRow>[] = [
    { key: 'stage', header: 'Stage', width: proportional(1), renderCell: (row) => <Text type="label">{row.stage}</Text> },
    { key: 'trace', header: `Approach ${approach.id}`, width: proportional(3), renderCell: (row) => (row.trace ? <Text>{row.trace}</Text> : <Text type="supporting">not provided</Text>) },
  ]
  return (
    <VStack gap={1}>
      <Text>{`Scenario: ${example.scenario}`}</Text>
      <Text type="supporting">Written by the proponent for the scenario the coordinator picked.</Text>
      <Table data={rows} columns={columns} idKey="id" verticalAlign="top" dividers="rows" />
    </VStack>
  )
}

function ApproachDetail({ approach, comparison }: { approach: Approach; comparison: Comparison }) {
  const label = `${approach.id} · ${approach.title}`
  const { deploy, undo } = approach
  return (
    <VStack gap={4}>
      <Card padding={2}>
        <VStack gap={1}>
          <HStack gap={1} align="center" wrap="wrap">
            <Text type="label" color="secondary">Overview</Text>
            <Token size="sm" color="default" label="Coordinator summary" description="Written by the coordinator, in neutral terms." />
          </HStack>
          <Text>{approach.overview}</Text>
        </VStack>
      </Card>

      <Section title="Worked example">
        <WorkedExample approach={approach} example={comparison.example} />
      </Section>

      <Section title="Repos touched">
        {approach.repos.length === 0 ? <NotProvided /> : (
          <HStack gap={1} wrap="wrap">
            {approach.repos.map((repo) => <Token key={repo.name} size="sm" color="default" label={`${repo.name} · ${repo.files} ${repo.files === 1 ? 'file' : 'files'}`} />)}
          </HStack>
        )}
      </Section>

      <Section title="Process flow">
        {approach.flow && approach.flow.length > 0 ? <ProcessFlow approach={approach} flowStages={comparison.flowStages ?? []} approachLabel={label} /> : <NotProvided />}
      </Section>

      <Section title="Runtime sequence">
        {approach.sequence && approach.sequence.participants.length > 0 ? <SequenceDiagram approach={approach} approachLabel={label} /> : <NotProvided />}
      </Section>

      <Section title="Schema">
        {approach.schema && approach.schema.tables.length > 0 ? <SchemaDiagram approach={approach} approachLabel={label} /> : <NotProvided />}
      </Section>

      <Section title="Deploy order">
        <VStack gap={1}>
          <HStack><Token size="sm" color={deploy.status === 'not-stated' ? 'default' : deploy.status === 'stated' ? 'green' : 'yellow'} label={DEPLOY_LABEL[deploy.status]} /></HStack>
          {deploy.steps.length > 0 ? (
            <ol style={{ margin: 0, paddingInlineStart: 20 }}>{deploy.steps.map((step, index) => <li key={index}><Text>{step}</Text></li>)}</ol>
          ) : <Text type="supporting">The spec doesn't give one.</Text>}
        </VStack>
      </Section>

      <Section title="Rests on">
        {approach.restsOn && approach.restsOn.length > 0 ? (
          <ul style={{ margin: 0, paddingInlineStart: 20 }}>{approach.restsOn.map((item, index) => <li key={index}><Text>{item}</Text></li>)}</ul>
        ) : <NotProvided />}
      </Section>

      <Section title="Undo and evolve">
        {undo ? (
          <VStack gap={1}>
            <Text><Text type="label">Flag off: </Text>{undo.flagOff}</Text>
            <Text><Text type="label">Hard to reverse: </Text>{undo.hardToReverse}</Text>
            <Text><Text type="label">Cheapest next step: </Text>{undo.cheapestNext}</Text>
          </VStack>
        ) : <NotProvided />}
      </Section>

      <Section title="Full tech spec">
        {approach.specMarkdown ? (
          <Collapsible trigger={`Approach ${approach.id} spec (markdown)`} defaultIsOpen={false}>
            <Card>
              <Markdown components={SPEC_MARKDOWN_COMPONENTS} headingLevelStart={2} contentWidth="100%">
                {approach.specMarkdown}
              </Markdown>
            </Card>
          </Collapsible>
        ) : <NotProvided />}
      </Section>
    </VStack>
  )
}

/** One approach at a time: pills switch between them, each showing the coordinator's summary then the proponent's own material. */
export function ApproachesView(props: CompareViewProps) {
  const { comparison, approaches } = props
  const shown = comparison.approaches.filter((approach) => approaches.includes(approach.id))
  const [selected, setSelected] = useState(shown[0]?.id ?? '')
  const current = shown.find((approach) => approach.id === selected) ?? shown[0]
  if (!current) return <Text type="supporting">No approaches to show.</Text>

  return (
    <VStack gap={3}>
      <Heading level={2}>Approaches</Heading>
      <div style={{ overflowX: 'auto' }}>
        <SegmentedControl label="Approach" value={current.id} onChange={setSelected}>
          {shown.map((approach) => <SegmentedControlItem key={approach.id} value={approach.id} label={`${approach.id} · ${approach.title}`} />)}
        </SegmentedControl>
      </div>
      <ApproachDetail key={current.id} approach={current} comparison={comparison} />
    </VStack>
  )
}
