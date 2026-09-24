import { useState } from 'react'
import { Heading } from '@astryxdesign/core/Heading'
import { Card, HStack, Layout, LayoutContent, LayoutPanel, VStack } from '@astryxdesign/core/Layout'
import { List, ListItem } from '@astryxdesign/core/List'
import { ProgressBar } from '@astryxdesign/core/ProgressBar'
import { Text } from '@astryxdesign/core/Text'
import type { LogicSpec, ReviewState } from '../spec-types'
import type { Update } from '../review-state'
import { isAwaitingCall, isClaudeItem } from './board-model'
import { RequirementDetail } from './requirement-dialog'

type Props = { spec: LogicSpec; state: ReviewState; update: Update; changedIds: Set<string> }

/** The requirements Claude wrote without asking, still waiting for a reviewer call: a list on the left, the selected one on the right. Placed items leave the list, and the section goes once every item is placed. */
export function CallQueue({ spec, state, update, changedIds }: Props) {
  const queue = spec.requirements.filter(isClaudeItem)
  const awaiting = queue.filter((requirement) => isAwaitingCall(state, requirement))
  const [selectedId, setSelectedId] = useState<string | undefined>(() => awaiting[0]?.id)
  const selected = awaiting.find((requirement) => requirement.id === selectedId) ?? awaiting[0]
  const placed = queue.length - awaiting.length
  if (!selected) return null

  return (
    <Card padding={0}>
      <VStack gap={0}>
        <VStack gap={1} padding={3}>
          <HStack gap={2} align="center">
            <Heading level={3}>Awaiting your call</Heading>
            <Text type="supporting" hasTabularNumbers>{awaiting.length}</Text>
          </HStack>
          <Text type="supporting">
            Claude wrote these {queue.length} requirements without asking you. Each shows Claude's recommendation; you decide whether it is in
            scope. Placed items move onto the board below.
          </Text>
          <ProgressBar label={`${placed} of ${queue.length} placed`} value={placed} max={queue.length} />
        </VStack>
        <Layout
          height="auto"
          defaultHasDividers
          start={
            <LayoutPanel width={400} hasDivider padding={0} label="Items awaiting your call" isScrollable={false}>
              <List hasDividers density="compact">
                {awaiting.map((requirement) => (
                  <ListItem
                    key={requirement.id}
                    label={`${requirement.id} · ${requirement.area}`}
                    description={requirement.summary}
                    isSelected={requirement.id === selected.id}
                    onClick={() => setSelectedId(requirement.id)}
                  />
                ))}
              </List>
            </LayoutPanel>
          }
          content={
            <LayoutContent padding={4} isScrollable={false} label="Selected item">
              <RequirementDetail key={selected.id} requirement={selected} spec={spec} state={state} update={update} changedIds={changedIds} headingLevel={3} />
            </LayoutContent>
          }
        />
      </VStack>
    </Card>
  )
}
