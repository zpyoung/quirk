import type { ReactNode } from 'react'
import { Collapsible } from '@astryxdesign/core/Collapsible'
import { Heading } from '@astryxdesign/core/Heading'
import { Card, HStack, VStack } from '@astryxdesign/core/Layout'
import { Text } from '@astryxdesign/core/Text'
import { Token } from '@astryxdesign/core/Token'
import { Tooltip } from '@astryxdesign/core/Tooltip'
import type { Approach, CompareViewProps } from '../../compare-types'

function Section({ title, badge, children }: { title: string; badge?: ReactNode; children: ReactNode }) {
  return (
    <VStack gap={2}>
      <HStack gap={2} align="center" wrap="wrap">
        <Heading level={3}>{title}</Heading>
        {badge}
      </HStack>
      {children}
    </VStack>
  )
}

function RiskChips({ approach }: { approach: Approach }) {
  if (!approach.slices.length) return <Text type="supporting">No slices provided.</Text>
  return (
    <HStack gap={1} wrap="wrap">
      {approach.slices.map((slice) => (
        <Tooltip key={slice.id} content={`${approach.id} wrote: ${slice.risk}`}>
          {slice.riskHeadline
            ? <Token size="sm" color="purple" label={slice.riskHeadline} description={`Coordinator headline for ${slice.name}`} />
            : <Token size="sm" color="default" label={`${slice.name} (headline not provided)`} description={`The coordinator gave no risk headline for ${slice.name}`} />}
        </Tooltip>
      ))}
    </HStack>
  )
}

/** Where the approaches differ in risk. Pairings and risk headlines are the coordinator's wording; rival claims are the proponents' advocacy. */
export function TradeoffsView(props: CompareViewProps) {
  const { comparison } = props
  const approaches = comparison.approaches.filter((approach) => props.approaches.includes(approach.id))
  const focused = new Set(props.approaches)
  const keyDifferences = comparison.keyDifferences ?? []
  const pairings = (comparison.pairings ?? []).filter((pairing) => Object.keys(pairing.items).filter((id) => focused.has(id)).length >= Math.min(2, focused.size))

  const claims = approaches.flatMap((claimant) =>
    Object.entries(claimant.rivalClaims ?? {})
      .filter(([targetId, items]) => focused.has(targetId) && items.length > 0)
      .map(([targetId, items]) => ({ claimant: claimant.id, target: targetId, items })),
  )

  return (
    <VStack gap={4}>
      <Heading level={2}>Trade-offs</Heading>

      {keyDifferences.length ? (
        <Section title="Key differences">
          <ul style={{ margin: 0, paddingInlineStart: 20 }}>{keyDifferences.map((item, index) => <li key={index}><Text>{item}</Text></li>)}</ul>
        </Section>
      ) : null}

      {pairings.length ? (
        <Section title="Same exposure" badge={<Token size="sm" color="purple" label="Coordinator-marked" description="The coordinator linked these risks across approaches; the proponents did not." />}>
          <VStack gap={2}>
            {pairings.map((pairing, index) => (
              <Card key={index} padding={2}>
                <VStack gap={1}>
                  <Text type="label">{pairing.name}</Text>
                  <Text>{pairing.text}</Text>
                  <ul style={{ margin: 0, paddingInlineStart: 20 }}>
                    {Object.entries(pairing.items).filter(([id]) => focused.has(id)).map(([id, text]) => <li key={id}><Text>{`${id}: ${text}`}</Text></li>)}
                  </ul>
                </VStack>
              </Card>
            ))}
          </VStack>
        </Section>
      ) : null}

      <Section title="Risks by approach" badge={<Token size="sm" color="purple" label="Purple chips are coordinator headlines" description="Hover a chip for the proponent's own words." />}>
        <div style={{ display: 'grid', gap: 12, gridTemplateColumns: `repeat(${Math.max(1, approaches.length)}, minmax(220px, 1fr))`, overflowX: 'auto' }}>
          {approaches.map((approach) => (
            <Card key={approach.id} padding={2}>
              <VStack gap={2}>
                <Text type="label">{`Approach ${approach.id} · ${approach.title}`}</Text>
                <RiskChips approach={approach} />
              </VStack>
            </Card>
          ))}
        </div>
      </Section>

      {claims.length ? (
        <Collapsible trigger="Rival claims (advocacy from each proponent, not findings)" defaultIsOpen={false}>
          <VStack gap={3}>
            <Token size="sm" color="orange" label="Advocacy" description="Each proponent argues against the others; the coordinator has not checked these." />
            {claims.map((group) => (
              <VStack key={`${group.claimant}-${group.target}`} gap={1}>
                <Text type="label">{`${group.claimant} on ${group.target}`}</Text>
                <ul style={{ margin: 0, paddingInlineStart: 20 }}>{group.items.map((item, index) => <li key={index}><Text>{item}</Text></li>)}</ul>
              </VStack>
            ))}
          </VStack>
        </Collapsible>
      ) : null}
    </VStack>
  )
}
