import { Button } from '@astryxdesign/core/Button'
import { Heading } from '@astryxdesign/core/Heading'
import { Card, HStack, VStack } from '@astryxdesign/core/Layout'
import { Text } from '@astryxdesign/core/Text'
import { Token } from '@astryxdesign/core/Token'
import type { CompareViewProps, Draft, TabKey } from '../../compare-types'
import { checkedScoreCounts, guidanceNotes, targetHash } from '../../compare-state'

const TAB_LABEL: Record<TabKey, string> = { overview: 'Overview', approaches: 'Approaches', effort: 'Effort', blast: 'Blast radius', tradeoffs: 'Trade-offs' }
const CONFIDENCE_COLOR = { low: 'orange', medium: 'yellow', high: 'green' } as const

function newDraftId(index: number): string {
  return `draft-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}-${index}`
}

function Bullets({ label, items }: { label: string; items: string[] }) {
  if (!items.length) return null
  return (
    <VStack gap={1}>
      <Text type="label" color="secondary">{label}</Text>
      <ul style={{ margin: 0, paddingInlineStart: 20 }}>
        {items.map((item, index) => <li key={index}><Text>{item}</Text></li>)}
      </ul>
    </VStack>
  )
}

/** The coordinator's walkthrough and recommendation. It is opinion, kept apart from the factual findings on the other tabs. */
export function GuidanceView(props: CompareViewProps) {
  const { comparison, spec, state, update, goToTab } = props
  const guidance = comparison.guidance
  if (!guidance) return <Text type="supporting">The coordinator did not write guidance for this comparison.</Text>

  const { recommendation } = guidance
  const picked = comparison.approaches.find((approach) => approach.id === recommendation.approachId)
  const notes = guidanceNotes(comparison, spec, state)
  const { checked, total } = checkedScoreCounts(comparison, spec, state)

  const draftedKeys = new Set(
    state.drafts.filter((draft) => draft.target.type === 'score').map((draft) => (draft.target.type === 'score' ? `${draft.target.requirementId}|${draft.target.approachId}` : '')),
  )
  const pending = guidance.suggestedChallenges.filter((item) => {
    const score = comparison.scores[item.requirementId]?.[item.approachId]
    return Boolean(score) && !draftedKeys.has(`${item.requirementId}|${item.approachId}`)
  })

  const draftThese = () => {
    const additions: Draft[] = []
    pending.forEach((item, index) => {
      const score = comparison.scores[item.requirementId]?.[item.approachId]
      if (!score) return
      additions.push({
        id: newDraftId(index),
        target: { type: 'score', requirementId: item.requirementId, approachId: item.approachId },
        note: item.note,
        want: item.want,
        targetHash: targetHash(score, 'score'),
      })
    })
    if (!additions.length) return
    update((draft) => {
      const taken = new Set(draft.drafts.map((existing) => (existing.target.type === 'score' ? `${existing.target.requirementId}|${existing.target.approachId}` : '')))
      for (const addition of additions) {
        if (addition.target.type !== 'score') continue
        const key = `${addition.target.requirementId}|${addition.target.approachId}`
        if (taken.has(key)) continue
        taken.add(key)
        draft.drafts.push(addition)
      }
    })
  }

  return (
    <VStack gap={4}>
      <VStack gap={1}>
        <HStack gap={2} align="center" wrap="wrap">
          <Heading level={2}>Guidance</Heading>
          <Token size="sm" color="purple" label="Coordinator's opinion" description="The one place on this page where the coordinator states a preference. Findings elsewhere are factual." />
        </HStack>
        <Text>{guidance.intro}</Text>
      </VStack>

      <VStack gap={2}>
        <Heading level={3}>Four things to read first</Heading>
        <ol style={{ margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 'var(--spacing-2, 8px)' }}>
          {guidance.steps.map((step, index) => (
            <li key={index}>
              <Card padding={2}>
                <VStack gap={1}>
                  <Text type="label">{`${index + 1}. ${step.title}`}</Text>
                  <Text>{step.body}</Text>
                  <HStack><Button size="sm" label={`See it on the ${TAB_LABEL[step.tab]} tab`} onClick={() => goToTab(step.tab)} /></HStack>
                </VStack>
              </Card>
            </li>
          ))}
        </ol>
      </VStack>

      {guidance.questions.length ? <Bullets label="Questions for you" items={guidance.questions} /> : null}

      <Card padding={3} variant="blue">
        <VStack gap={3}>
          <VStack gap={1}>
            <HStack gap={2} align="center" wrap="wrap">
              <Text type="label" color="secondary">Recommendation</Text>
              <Token size="sm" color="purple" label="Coordinator's opinion" />
            </HStack>
            <Heading level={3}>{`Approach ${recommendation.approachId}${picked ? ` · ${picked.title}` : ''}`}</Heading>
            <Text>{recommendation.headline}</Text>
          </VStack>
          <HStack gap={2} align="center" wrap="wrap">
            <Token size="sm" color={CONFIDENCE_COLOR[recommendation.confidence]} label={`Confidence: ${recommendation.confidence}`} />
            <Text type="supporting">{recommendation.confidenceReason}</Text>
            <Text type="supporting">{`${checked} of ${total} scores checked`}</Text>
          </HStack>
          <Bullets label="Why" items={recommendation.why} />
          <Bullets label="What it costs" items={recommendation.costs} />
          <Bullets label="What would change my mind" items={recommendation.changeMyMind} />
          {guidance.changeNote ? (
            <VStack gap={1}>
              <Text type="label" color="secondary">What changed since the last round</Text>
              <Text>{guidance.changeNote}</Text>
            </VStack>
          ) : null}
          {notes.length ? (
            <VStack gap={1}>
              <Text type="label" color="secondary">From your view</Text>
              <ul style={{ margin: 0, paddingInlineStart: 20 }} aria-live="polite">
                {notes.map((note, index) => <li key={index}><Text>{note}</Text></li>)}
              </ul>
            </VStack>
          ) : null}
        </VStack>
      </Card>

      {guidance.suggestedChallenges.length ? (
        <VStack gap={2}>
          <Heading level={3}>Before you decide</Heading>
          <Text type="supporting">Scores the coordinator would push on. Drafting them adds editable challenges to your tray; nothing is sent until you export.</Text>
          <ul style={{ margin: 0, paddingInlineStart: 20 }}>
            {guidance.suggestedChallenges.map((item, index) => (
              <li key={index}>
                <Text>{`${item.requirementId} on approach ${item.approachId} (wanted: ${item.want}): ${item.note}`}</Text>
              </li>
            ))}
          </ul>
          <HStack gap={2} align="center" wrap="wrap">
            <Button variant="primary" label="Draft these" isDisabled={pending.length === 0} onClick={draftThese} />
            {pending.length === 0 ? <Text type="supporting">All of these are already drafted.</Text> : null}
          </HStack>
        </VStack>
      ) : null}
    </VStack>
  )
}
