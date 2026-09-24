import { Children, type ReactNode } from 'react'
import { Banner } from '@astryxdesign/core/Banner'
import type { CardVariant } from '@astryxdesign/core/Card'
import { Grid } from '@astryxdesign/core/Grid'
import { Heading } from '@astryxdesign/core/Heading'
import { Card, HStack, StackItem, VStack } from '@astryxdesign/core/Layout'
import { Link } from '@astryxdesign/core/Link'
import { Text } from '@astryxdesign/core/Text'
import { CERTAINTIES, GROUPS, GROUP_LABEL, placedRequirements } from '../review-state'
import type { Certainty, Requirement, RequirementGroup } from '../spec-types'
import { CERTAINTY_LABEL } from './shared'
import type { ViewProps } from './view-props'

const ROW_LABEL_WIDTH = 96
const HIGH_IMPACT: RequirementGroup[] = ['min', 'i3']

/** Risk climbs toward the top right: high-impact groups crossed with unverified certainty. */
function riskVariant(group: RequirementGroup, certainty: Certainty): CardVariant {
  const highImpact = HIGH_IMPACT.includes(group)
  if (certainty === 'confirmed') return 'green'
  if (certainty === 'assumed') return highImpact ? 'orange' : group === 'i2' ? 'yellow' : 'green'
  return highImpact ? 'red' : group === 'i2' ? 'orange' : 'yellow'
}

/** One heatmap row: a narrow fixed label column, then the certainty cells sharing the remaining width. */
function GridRow({ label, children }: { label: ReactNode; children: ReactNode }) {
  return (
    <HStack gap={2}>
      <VStack width={ROW_LABEL_WIDTH}>{label}</VStack>
      <StackItem size="fill">
        <Grid columns={Children.count(children)} gap={2}>
          {children}
        </Grid>
      </StackItem>
    </HStack>
  )
}

function GridCell({ variant, items, onOpen }: { variant: CardVariant; items: Requirement[]; onOpen: () => void }) {
  return (
    <Card variant={variant} padding={2}>
      <VStack gap={1}>
        <Text type="label" color="secondary">
          {items.length} requirement{items.length === 1 ? '' : 's'}
        </Text>
        {items.map((requirement) => (
          <Link key={requirement.id} onClick={onOpen}>
            {requirement.id} · {requirement.summary}
          </Link>
        ))}
      </VStack>
    </Card>
  )
}

/** Requirements grouped by impact and certainty, so the reviewer sees what still needs checking before anything is built. */
export function ImpactCertaintyView({ spec, state, onNavigate }: ViewProps) {
  const placed = placedRequirements(spec, state).filter(({ requirement, placement }) => placement !== 'out' && requirement.certainty !== null)
  const outCount = spec.requirements.length - placed.length
  const openOnBoard = () => onNavigate('board')
  const checkFirst = placed.filter(
    ({ requirement }) => HIGH_IMPACT.includes(requirement.group) && (requirement.certainty === 'assumed' || requirement.certainty === 'unverified'),
  )
  const cellItems = (group: RequirementGroup, certainty: Certainty) =>
    placed.filter(({ requirement }) => requirement.group === group && requirement.certainty === certainty).map(({ requirement }) => requirement)

  return (
    <VStack gap={4}>
      <VStack gap={1}>
        <Heading level={2}>Impact × certainty</Heading>
        <Text type="supporting" as="p">
          What to check before building: in-scope requirements grouped by how much a mistake would cost (rows) and how sure Claude is about them (columns).
          Risk climbs toward the top right — high-impact requirements nobody has verified. Click any requirement to open it on the Scope board.
          {outCount > 0 ? ` ${outCount} out-of-scope requirement${outCount === 1 ? ' is' : 's are'} left out of this grid.` : ''}
        </Text>
      </VStack>

      {checkFirst.length > 0 ? (
        <Banner status="warning" title="Check before building" collapsible={false}>
          <VStack gap={1}>
            {checkFirst.map(({ requirement }) => {
              const affects = spec.assumptions
                .filter((assumption) => assumption.affects.some((id) => requirement.derivedFrom.includes(id)))
                .map((assumption) => assumption.id)
              return (
                <Text key={requirement.id}>
                  <Link onClick={openOnBoard}>{requirement.id}</Link> — {requirement.summary} ({CERTAINTY_LABEL[requirement.certainty as Certainty]}
                  {affects.length > 0 ? `, rests on ${affects.join(', ')}` : ', no tracked assumption'})
                </Text>
              )
            })}
          </VStack>
        </Banner>
      ) : null}

      <VStack gap={2}>
        <GridRow label={null}>
          {CERTAINTIES.map((certainty) => (
            <Text key={certainty} type="label">
              {CERTAINTY_LABEL[certainty]}
            </Text>
          ))}
        </GridRow>
        {GROUPS.map((group) => (
          <GridRow key={group} label={<Text type="label">{GROUP_LABEL[group]}</Text>}>
            {CERTAINTIES.map((certainty) => (
              <GridCell key={certainty} variant={riskVariant(group, certainty)} items={cellItems(group, certainty)} onOpen={openOnBoard} />
            ))}
          </GridRow>
        ))}
      </VStack>
    </VStack>
  )
}
