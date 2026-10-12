import { useState } from 'react'
import { Button } from '@astryxdesign/core/Button'
import { Collapsible } from '@astryxdesign/core/Collapsible'
import { Dialog, DialogHeader } from '@astryxdesign/core/Dialog'
import { Divider } from '@astryxdesign/core/Divider'
import { Heading } from '@astryxdesign/core/Heading'
import { Card, HStack, VStack } from '@astryxdesign/core/Layout'
import { Selector } from '@astryxdesign/core/Selector'
import { Text } from '@astryxdesign/core/Text'
import { TextArea } from '@astryxdesign/core/TextArea'
import { Token } from '@astryxdesign/core/Token'
import { POINT_MAP, staleScore, targetHash } from '../../compare-state'
import type { CompareState, Comparison, CompareViewProps, Draft, Finding, Score, ScoreHistory, ScoreStatus, SizeLabel } from '../../compare-types'
import { CONDITION_LABEL } from '../../review-state'
import { STATUS_META, STATUS_ORDER, StatusChip } from './status-chip'

/** Findings on one requirement that name this approach, directly or through `"all"`. */
export function findingsFor(comparison: Comparison, requirementId: string, approachId: string): Finding[] {
  return (comparison.findings ?? []).filter(
    (finding) => finding.requirementId === requirementId && (finding.approaches === 'all' || finding.approaches.includes(approachId)),
  )
}

/** The most recent challenge answer on a score, or null when it was never challenged. */
export function latestHistory(score: Score): ScoreHistory | null {
  const history = score.history ?? []
  return history.length > 0 ? history[history.length - 1]! : null
}

/** First sentence of a note; the whole note when it has no sentence break. */
export function firstSentence(note: string): string {
  const text = note.trim()
  const match = /^[\s\S]*?[.!?](?=\s|$)/.exec(text)
  return match ? match[0] : text
}

let draftCounter = 0
export const newDraftId = () => `c-${Date.now().toString(36)}-${(draftCounter++).toString(36)}-${Math.random().toString(36).slice(2, 6)}`

const WANT_OPTIONS: { value: string; label: string }[] = STATUS_ORDER.map((status) => ({ value: status, label: STATUS_META[status].label }))
export const SIZE_OPTIONS: { value: string; label: string }[] = (Object.keys(POINT_MAP) as SizeLabel[]).map((size) => ({ value: size, label: size }))

/** Replaces a draft's note and wanted value in place, leaving its id, target and targetHash untouched. */
export function saveDraftEdit(update: CompareViewProps['update'], list: 'drafts' | 'needsLook', id: string, note: string, want: Draft['want']): void {
  update((s: CompareState) => {
    s[list] = s[list].map((draft) => (draft.id === id ? { ...draft, note, want } : draft))
  })
}

/** One draft with its note and wanted value, editable in place; `children` are the row's extra actions such as Remove. */
export function DraftCard({ draft, heading, onSave, children, bare = false }: { draft: Draft; heading: string; onSave: (note: string, want: Draft['want']) => void; children?: React.ReactNode; bare?: boolean }) {
  const [editing, setEditing] = useState(false)
  const [note, setNote] = useState(draft.note)
  const [want, setWant] = useState<string>(draft.want)
  const isScore = draft.target.type === 'score'
  const wantLabel = isScore ? (STATUS_META[draft.want as ScoreStatus]?.label ?? draft.want) : draft.want
  const body = editing ? (
    <VStack gap={2}>
      <Text type="label" color="secondary">{heading}</Text>
      <TextArea label="Note" rows={3} value={note} onChange={setNote} isRequired />
      <Selector
        label={isScore ? 'Score you think is right' : 'Size you think is right'}
        value={want}
        onChange={(value) => setWant(value as string)}
        options={isScore ? [...WANT_OPTIONS] : [...SIZE_OPTIONS]}
      />
      <HStack gap={1}>
        <Button
          variant="primary"
          size="sm"
          label="Save"
          isDisabled={note.trim() === ''}
          onClick={() => {
            onSave(note.trim(), want as Draft['want'])
            setEditing(false)
          }}
        />
        <Button
          variant="secondary"
          size="sm"
          label="Cancel"
          onClick={() => {
            setNote(draft.note)
            setWant(draft.want)
            setEditing(false)
          }}
        />
      </HStack>
    </VStack>
  ) : (
    <HStack gap={2} align="start" justify="between" wrap="wrap">
      <VStack gap={0.5} style={{ flex: '1 1 220px', minWidth: 0 }}>
        <Text type="label" color="secondary">{`${heading} · wants ${wantLabel}`}</Text>
        <Text>{draft.note}</Text>
      </VStack>
      <HStack gap={1}>
        <Button variant="secondary" size="sm" label="Edit" aria-label={`Edit draft: ${heading}`} onClick={() => { setNote(draft.note); setWant(draft.want); setEditing(true) }} />
        {children}
      </HStack>
    </HStack>
  )
  return bare ? body : <Card padding={2}>{body}</Card>
}
const FINDING_COLOR = { disputes: 'orange', 'same score, different design': 'blue' } as const

function sameScoreTarget(draft: Draft, requirementId: string, approachId: string): boolean {
  return draft.target.type === 'score' && draft.target.requirementId === requirementId && draft.target.approachId === approachId
}

/** Note plus the wanted status for one score; saving appends a draft aimed at that score's current content. */
function ChallengeForm({ requirementId, approachId, score, state, update }: { requirementId: string; approachId: string; score: Score } & Pick<CompareViewProps, 'state' | 'update'>) {
  const [note, setNote] = useState('')
  const [want, setWant] = useState<ScoreStatus>(score.status === 'met' ? 'not met' : 'met')
  const existing = state.drafts.filter((draft) => sameScoreTarget(draft, requirementId, approachId))

  const save = () => {
    const draft: Draft = {
      id: newDraftId(),
      target: { type: 'score', requirementId, approachId },
      note: note.trim(),
      want,
      targetHash: targetHash(score, 'score'),
    }
    update((s) => {
      s.drafts = [...s.drafts, draft]
    })
    setNote('')
  }
  const remove = (id: string) =>
    update((s) => {
      s.drafts = s.drafts.filter((draft) => draft.id !== id)
    })

  return (
    <VStack gap={2}>
      <Heading level={5}>Challenge</Heading>
      {existing.map((draft) => (
        <DraftCard key={draft.id} draft={draft} heading={`Draft on ${requirementId} for approach ${approachId}`} onSave={(text, value) => saveDraftEdit(update, 'drafts', draft.id, text, value)}>
          <Button variant="secondary" size="sm" label="Remove" aria-label={`Remove draft challenge on ${requirementId} for approach ${approachId}`} onClick={() => remove(draft.id)} />
        </DraftCard>
      ))}
      <TextArea label="Why this score is wrong" rows={3} value={note} onChange={setNote} isRequired />
      <Selector label="Score you think is right" value={want} onChange={(value) => setWant(value as ScoreStatus)} options={WANT_OPTIONS} />
      <HStack>
        <Button variant="primary" label="Add challenge" isDisabled={note.trim() === ''} onClick={save} />
      </HStack>
    </VStack>
  )
}

function StaleDiff({ oldText, newText }: { oldText: string; newText: string }) {
  return (
    <Card padding={2}>
      <VStack gap={1}>
        <Token size="sm" color="yellow" label="Scored against older text" />
        <Text type="label" color="secondary">Text when scored</Text>
        <div style={{ background: 'var(--color-background-red)', color: 'var(--color-text-red)', padding: '4px 8px', borderRadius: 6 }}>
          <Text>{oldText}</Text>
        </div>
        <Text type="label" color="secondary">Signed text now</Text>
        <div style={{ background: 'var(--color-background-green)', color: 'var(--color-text-green)', padding: '4px 8px', borderRadius: 6 }}>
          <Text>{newText}</Text>
        </div>
      </VStack>
    </Card>
  )
}

function HistoryTrail({ history }: { history: ScoreHistory[] }) {
  return (
    <VStack gap={1}>
      <Text type="label" color="secondary">After challenge</Text>
      {history.map((entry, index) => (
        <Card key={index} padding={2}>
          <VStack gap={1}>
            <HStack gap={1} align="center" wrap="wrap">
              <Text type="supporting">Was</Text>
              <StatusChip status={entry.previous.status} qualifier={entry.previous.qualifier} size="sm" />
              <Token size="sm" color={entry.outcome === 'revised' ? 'blue' : 'gray'} label={entry.outcome === 'revised' ? 'Revised after challenge' : 'Held after challenge'} />
            </HStack>
            <Text>{`Your challenge: ${entry.challenge}`}</Text>
            <Text>{`Proponent reply: ${entry.reply}`}</Text>
          </VStack>
        </Card>
      ))}
    </VStack>
  )
}

function ApproachSection({ approachId, requirementId, props }: { approachId: string; requirementId: string; props: CompareViewProps }) {
  const { comparison, spec, itemHashes, state, update } = props
  const approach = comparison.approaches.find((candidate) => candidate.id === approachId)
  const score = comparison.scores[requirementId]?.[approachId]
  if (!approach) return null
  if (!score) {
    return (
      <VStack gap={1}>
        <Heading level={4}>{`${approach.id} · ${approach.title}`}</Heading>
        <Text type="supporting">No score for this requirement.</Text>
      </VStack>
    )
  }
  const stale = staleScore(score, spec, itemHashes, requirementId)
  const findings = findingsFor(comparison, requirementId, approachId)
  const wordingDiffers = score.wording.trim().toLowerCase() !== STATUS_META[score.status].label.toLowerCase()
  const summary = firstSentence(score.note)

  return (
    <VStack gap={2}>
      <HStack gap={2} align="center" wrap="wrap">
        <Heading level={4}>{`${approach.id} · ${approach.title}`}</Heading>
        <StatusChip status={score.status} qualifier={score.qualifier} />
      </HStack>
      {wordingDiffers ? <Text type="supporting">{`Proponent wording: "${score.wording}"`}</Text> : null}
      {summary ? <Text>{summary}</Text> : null}
      <Collapsible trigger="Full note and citations" defaultIsOpen={false}>
        <VStack gap={1}>
          <Text>{score.note}</Text>
          {score.citations.length > 0 ? (
            <VStack gap={0.5}>
              <Text type="label" color="secondary">Citations</Text>
              {score.citations.map((citation) => <Text key={citation} type="supporting">{citation}</Text>)}
            </VStack>
          ) : null}
        </VStack>
      </Collapsible>
      <Text type="supporting">{score.check ? `Checked: ${score.check}` : 'Claimed by the proponent; not checked.'}</Text>
      {findings.map((finding, index) => (
        <Card key={index} padding={2}>
          <VStack gap={1}>
            <Token size="sm" color={FINDING_COLOR[finding.type]} label={finding.type === 'disputes' ? 'Disputes' : 'Same score, different design'} />
            <Text>{finding.text}</Text>
            <Text type="supporting">{finding.citation}</Text>
          </VStack>
        </Card>
      ))}
      {stale.stale ? <StaleDiff oldText={stale.oldText} newText={stale.newText} /> : null}
      {score.history && score.history.length > 0 ? <HistoryTrail history={score.history} /> : null}
      <ChallengeForm key={`${requirementId}|${approachId}`} requirementId={requirementId} approachId={approachId} score={score} state={state} update={update} />
    </VStack>
  )
}

/** Right-side drawer for one requirement: the signed text, then each focused approach's score with its evidence, history and a challenge form. Closed when `requirementId` is null or unknown. */
export function ScoreDrawer(props: CompareViewProps & { requirementId: string | null; onClose: () => void }) {
  const { requirementId, onClose, spec, state, update, approaches } = props
  const requirement = requirementId === null ? undefined : spec.requirements.find((candidate) => candidate.id === requirementId)
  if (!requirement) return null
  const starred = state.stars.includes(requirement.id)
  const toggleStar = () =>
    update((s) => {
      s.stars = s.stars.includes(requirement.id) ? s.stars.filter((id) => id !== requirement.id) : [...s.stars, requirement.id]
    })

  return (
    <Dialog
      isOpen
      onOpenChange={(open) => !open && onClose()}
      width={560}
      maxHeight="100dvh"
      position={{ end: 0, top: 0, bottom: 0 }}
      purpose="form"
      style={{ height: '100dvh', borderRadius: 0 }}
    >
      <DialogHeader title={`${requirement.id} · ${requirement.summary}`} subtitle={requirement.area} onOpenChange={(open) => !open && onClose()} />
      <div style={{ flex: '1 1 auto', minHeight: 0, overflowY: 'auto' }}>
        <VStack gap={3} padding={4}>
          <VStack gap={1}>
            <HStack gap={1} align="center" wrap="wrap" justify="between">
              <HStack gap={1} align="center" wrap="wrap">
                <Text type="label" color="secondary">Signed requirement</Text>
                {requirement.condition ? <Token size="sm" color="blue" label="Conditional" description={CONDITION_LABEL[requirement.condition]} /> : null}
              </HStack>
              <Button
                variant={starred ? 'primary' : 'secondary'}
                size="sm"
                label={starred ? '★ Must-have' : '☆ Mark as must-have'}
                aria-pressed={starred}
                onClick={toggleStar}
              />
            </HStack>
            <Text>{requirement.text}</Text>
          </VStack>
          {approaches.map((approachId) => (
            <VStack key={approachId} gap={3}>
              <Divider />
              <ApproachSection approachId={approachId} requirementId={requirement.id} props={props} />
            </VStack>
          ))}
        </VStack>
      </div>
    </Dialog>
  )
}
