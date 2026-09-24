import type { ReactNode } from 'react'
import { HStack, VStack } from '@astryxdesign/core/Layout'
import { Markdown, type MarkdownComponents } from '@astryxdesign/core/Markdown'
import { Text } from '@astryxdesign/core/Text'
import { Token } from '@astryxdesign/core/Token'
import type { Certainty, Requirement, RequirementGroup } from '../spec-types'

export const CERTAINTY_LABEL: Record<Certainty, string> = { confirmed: 'Confirmed', assumed: 'Assumed', unverified: 'Unverified' }
export const CERTAINTY_COLOR = { confirmed: 'green', assumed: 'yellow', unverified: 'orange' } as const
export const GROUP_COLOR: Record<RequirementGroup, 'blue' | 'orange' | 'yellow' | 'cyan'> = { min: 'blue', i3: 'orange', i2: 'yellow', i1: 'cyan' }

/** Keeps the page offline: images in Claude-written markdown are named, never fetched. */
export const OFFLINE_MARKDOWN_COMPONENTS: MarkdownComponents = {
  image: ({ alt }) => <span>{alt ? `Image omitted in offline review: ${alt}` : 'Image omitted in offline review.'}</span>,
}

/** Renders markdown from logic.json with the offline image guard. */
export function SpecMarkdown({ children, compact }: { children: string; compact?: boolean }) {
  return (
    <Markdown components={OFFLINE_MARKDOWN_COMPONENTS} contentWidth="100%" density={compact ? 'compact' : undefined}>
      {children.replace(/_/g, '_​')}
    </Markdown>
  )
}

/** Marks copy Claude wrote, so the reviewer never mistakes it for their own decision. */
export function ClaudeWroteToken() {
  return <Token size="sm" color="default" label="Claude wrote this" description="Plain-language copy Claude wrote from the spec." />
}

/** A labelled, Claude-written markdown field: the label, the attribution, then the copy. */
export function ClaudeField({ label, children }: { label: string; children: string }) {
  return (
    <VStack gap={1}>
      <HStack gap={1} align="center" wrap="wrap">
        <Text type="label" color="secondary">{label}</Text>
        <ClaudeWroteToken />
      </HStack>
      <SpecMarkdown>{children}</SpecMarkdown>
    </VStack>
  )
}

/** A plain labelled field for reviewer-facing facts that are not Claude's copy. */
export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <VStack gap={1}>
      <Text type="label" color="secondary">{label}</Text>
      {typeof children === 'string' ? <Text>{children}</Text> : children}
    </VStack>
  )
}

export function ChangedToken({ id, changedIds, short }: { id: string; changedIds: Set<string>; short?: boolean }) {
  if (!changedIds.has(id)) return null
  return <Token size="sm" color="orange" label={short ? 'Changed' : 'Changed since you reviewed'} description="This item is new or changed since your last export; earlier decisions on it were cleared." />
}

export function ProvenanceToken({ requirement }: { requirement: Requirement }) {
  if (requirement.provenance === 'claude') {
    return <Token size="sm" color="red" label="Claude added this without asking you" description="Claude wrote this requirement itself; it never came up as a brainstorm question." />
  }
  const label = requirement.provenance === 'you-chose' ? 'You chose against the recommendation' : 'You took the recommendation'
  return <Token size="sm" color="default" label={label} description={requirement.question ? `Brainstorm question: ${requirement.question}` : undefined} />
}

export function CertaintyToken({ certainty }: { certainty: Certainty | null }) {
  if (!certainty) return null
  return <Token size="sm" color={CERTAINTY_COLOR[certainty]} label={CERTAINTY_LABEL[certainty]} />
}
