import type { ReactNode } from 'react'
import { HStack, VStack } from '@astryxdesign/core/Layout'
import { Markdown, type MarkdownComponents } from '@astryxdesign/core/Markdown'
import { Text } from '@astryxdesign/core/Text'
import type { TablePlugin } from '@astryxdesign/core/Table'
import { Token } from '@astryxdesign/core/Token'
import { VisuallyHidden } from '@astryxdesign/core/VisuallyHidden'
import type { Certainty, LogicSpec, Provenance, RequirementGroup } from '../spec-types'
import { ItemRef, useItemLinkPlugins } from './item-links'

export const CERTAINTY_LABEL: Record<Certainty, string> = { confirmed: 'Confirmed', assumed: 'Assumed', unverified: 'Unverified' }
export const CERTAINTY_COLOR = { confirmed: 'green', assumed: 'yellow', unverified: 'orange' } as const
export const GROUP_COLOR: Record<RequirementGroup, 'blue' | 'orange' | 'yellow' | 'cyan'> = { min: 'blue', i3: 'orange', i2: 'yellow', i1: 'cyan' }

/** Keeps the page offline: images in Claude-written markdown are named, never fetched. */
export const OFFLINE_MARKDOWN_COMPONENTS: MarkdownComponents = {
  image: ({ alt }) => <span>{alt ? `Image omitted in offline review: ${alt}` : 'Image omitted in offline review.'}</span>,
}

/** Renders markdown from logic.json with the offline image guard; item IDs in the text open that item's details. */
export function SpecMarkdown({ children, compact }: { children: string; compact?: boolean }) {
  const inlinePlugins = useItemLinkPlugins()
  return (
    <Markdown components={OFFLINE_MARKDOWN_COMPONENTS} inlinePlugins={inlinePlugins} contentWidth="100%" density={compact ? 'compact' : undefined}>
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

/** Tints the table rows whose `id` is in `changedIds`; pair it with ChangedRowLabel so the change is announced, not only seen. */
export function changedRowsPlugin<T extends Record<string, unknown>>(changedIds: Set<string>): TablePlugin<T> {
  return {
    transformBodyRow: (props, row) =>
      typeof row.id === 'string' && changedIds.has(row.id) ? { ...props, htmlProps: { ...props.htmlProps, 'data-changed': 'true' } as typeof props.htmlProps } : props,
  }
}

/** The screen-reader counterpart of a changed row's tint. */
export function ChangedRowLabel({ id, changedIds }: { id: string; changedIds: Set<string> }) {
  return changedIds.has(id) ? <VisuallyHidden>Changed since you reviewed</VisuallyHidden> : null
}

export function ProvenanceToken({ item }: { item: { provenance: Provenance; question?: string } }) {
  if (item.provenance === 'claude') {
    return <Token size="sm" color="red" label="Claude added this without asking you" description="Claude wrote this itself; it never came up as a brainstorm question." />
  }
  const label = item.provenance === 'you-chose' ? 'You chose against the recommendation' : 'You took the recommendation'
  return <Token size="sm" color="default" label={label} description={item.question ? `Brainstorm question: ${item.question}` : undefined} />
}

/** Marks a Claude-added scenario or constraint whose pick is shown selected but not yet confirmed by a state entry. */
export function PreselectedToken() {
  return <Token size="sm" color="blue" label="Preselected — confirm" description="Claude's pick is shown selected. Decide it to confirm, even if you keep the same pick." />
}

export function CertaintyToken({ certainty }: { certainty: Certainty | null }) {
  if (!certainty) return null
  return <Token size="sm" color={CERTAINTY_COLOR[certainty]} label={CERTAINTY_LABEL[certainty]} />
}

/** An item's short label for referencing it by ID from elsewhere in the review. */
export function itemLabel(spec: LogicSpec, id: string): string {
  const scenario = spec.scenarios.find((s) => s.id === id)
  if (scenario) return scenario.then
  const constraint = spec.constraints.find((c) => c.id === id)
  if (constraint) return constraint.text
  const other = spec.assumptions.find((a) => a.id === id)?.claim ??
    spec.blindSpots.find((b) => b.id === id)?.title ??
    spec.requirements.find((r) => r.id === id)?.summary ??
    spec.behaviors.find((b) => b.id === id)?.rule
  return other ?? id
}

/** One referenced item as a line of prose: its linked ID, then its short label. */
export function ItemReference({ spec, id }: { spec: LogicSpec; id: string }) {
  return <Text><ItemRef id={id} />{` · ${itemLabel(spec, id)}`}</Text>
}
