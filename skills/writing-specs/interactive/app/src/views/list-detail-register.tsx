import { type ReactNode } from 'react'
import { Button } from '@astryxdesign/core/Button'
import { Card, HStack, Layout, LayoutContent, LayoutPanel, VStack } from '@astryxdesign/core/Layout'
import { List, ListItem } from '@astryxdesign/core/List'
import { ProgressBar } from '@astryxdesign/core/ProgressBar'
import { Text } from '@astryxdesign/core/Text'

export type RegisterEntry = { id: string; label: string; description: string; status: ReactNode; isDone: boolean }

type Props = {
  intro: string
  doneLabel: string
  listLabel: string
  nextLabel: string
  entries: RegisterEntry[]
  selectedId: string
  onSelect: (id: string) => void
  detail: ReactNode
}

/** Open entries first, done entries after, each group keeping its given order. */
function openFirst(entries: RegisterEntry[]): RegisterEntry[] {
  return [...entries.filter((e) => !e.isDone), ...entries.filter((e) => e.isDone)]
}

/** The open entry to select once `id` is decided: the next one below it in the list, else the first still open. */
export function nextOpenEntryId(entries: RegisterEntry[], id: string): string | undefined {
  const ordered = openFirst(entries)
  const position = ordered.findIndex((e) => e.id === id)
  const remaining = ordered.filter((e) => e.id !== id && !e.isDone)
  return (remaining.find((e) => ordered.indexOf(e) > position) ?? remaining[0])?.id
}

/** A card with progress on top, every entry listed on the left with done ones sunk to the end, and the selected entry's detail on the right. */
export function ListDetailRegister({ intro, doneLabel, listLabel, nextLabel, entries, selectedId, onSelect, detail }: Props) {
  const ordered = openFirst(entries)
  const done = entries.filter((e) => e.isDone).length
  const selected = entries.find((e) => e.id === selectedId)
  const next = ordered.find((e) => !e.isDone && e.id !== selectedId)
  return (
    <Card padding={0}>
      <VStack gap={0}>
        <VStack gap={1} padding={3}>
          <Text type="supporting">{intro}</Text>
          <ProgressBar label={`${done} of ${entries.length} ${doneLabel}`} value={done} max={entries.length} />
        </VStack>
        <Layout
          height="auto"
          defaultHasDividers
          start={
            <LayoutPanel width={400} hasDivider padding={0} label={listLabel} isScrollable={false}>
              <List hasDividers density="compact">
                {ordered.map((e) => (
                  <ListItem
                    key={e.id}
                    label={e.label}
                    description={e.description}
                    isSelected={e.id === selectedId}
                    onClick={() => onSelect(e.id)}
                    endContent={e.status}
                  />
                ))}
              </List>
            </LayoutPanel>
          }
          content={
            <LayoutContent padding={4} isScrollable={false} label={`Selected: ${selected?.label ?? ''}`}>
              <VStack gap={4}>
                {detail}
                {next ? (
                  <HStack gap={2}>
                    <Button variant={selected?.isDone ? 'primary' : 'secondary'} label={`${nextLabel}: ${next.id}`} onClick={() => onSelect(next.id)} />
                  </HStack>
                ) : null}
              </VStack>
            </LayoutContent>
          }
        />
      </VStack>
    </Card>
  )
}
