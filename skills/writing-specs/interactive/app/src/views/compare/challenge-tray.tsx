import { useRef, useState } from 'react'
import { Button } from '@astryxdesign/core/Button'
import { Collapsible } from '@astryxdesign/core/Collapsible'
import { Card, HStack, VStack } from '@astryxdesign/core/Layout'
import { Text } from '@astryxdesign/core/Text'
import { Token } from '@astryxdesign/core/Token'
import { COMPARE_EXPORT_KIND, allHistoryCounts, allScoreHashes, createCompareExport, isCompareExport, partitionStars, targetHash } from '../../compare-state'
import type { Comparison, CompareExport, CompareState, Draft } from '../../compare-types'
import { EXPORT_KIND, localStamp, readPayload } from '../../review-state'
import { DraftCard, saveDraftEdit } from './score-drawer'

interface ChallengeTrayProps {
  slug: string
  renderId: string
  comparisonId: string
  comparison: Comparison
  state: CompareState
  update: (recipe: (draft: CompareState) => void) => void
}

/** The hash of what a draft's target says in the loaded comparison, or null when the target no longer exists. */
function currentHash(comparison: Comparison, draft: Draft): string | null {
  if (draft.target.type === 'score') {
    const score = comparison.scores[draft.target.requirementId]?.[draft.target.approachId]
    return score ? targetHash(score, 'score') : null
  }
  const { approachId, sliceId } = draft.target
  const slice = comparison.approaches.find((approach) => approach.id === approachId)?.slices.find((candidate) => candidate.id === sliceId)
  return slice ? targetHash(slice, 'slice') : null
}

function describeTarget(draft: Draft): string {
  return draft.target.type === 'score' ? `${draft.target.requirementId} on approach ${draft.target.approachId}` : `slice ${draft.target.sliceId} of approach ${draft.target.approachId}`
}

function DraftRow({ draft, list, update, children }: { draft: Draft; list: 'drafts' | 'needsLook'; update: ChallengeTrayProps['update']; children: React.ReactNode }) {
  return (
    <DraftCard bare draft={draft} heading={describeTarget(draft)} onSave={(note, want) => saveDraftEdit(update, list, draft.id, note, want)}>
      {children}
    </DraftCard>
  )
}

/** Bottom tray: draft counts, a way to settle drafts whose target changed, and the stage-3 export and import. */
export function ChallengeTray({ slug, renderId, comparisonId, comparison, state, update }: ChallengeTrayProps) {
  const [status, setStatus] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const exportChallenges = () => {
    const data = createCompareExport(slug, renderId, comparisonId, comparison, state)
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${slug}-challenges-${localStamp(new Date())}.json`
    anchor.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 0)
    update((draft) => {
      draft.lastExport = {
        at: data.exportedAt,
        approachRevisions: data.approachRevisions,
        scoreHashes: allScoreHashes(comparison),
        historyCounts: allHistoryCounts(comparison),
      }
    })
    setStatus(`Exported ${data.challenges.length} challenge${data.challenges.length === 1 ? '' : 's'} and ${data.stars.length} must-have${data.stars.length === 1 ? '' : 's'}.`)
  }

  const importFile = (file: File) => {
    void file.text().then((text) => {
      let parsed: unknown
      try { parsed = JSON.parse(text) } catch { setStatus('Import failed: file is not valid JSON.'); return }
      const kind = typeof parsed === 'object' && parsed !== null ? (parsed as { kind?: unknown }).kind : undefined
      if (kind === EXPORT_KIND) {
        setStatus(`Import failed: this is a stage 1-2 decisions export (kind "${EXPORT_KIND}"). Import it on the Sign-off tab, not here.`)
        return
      }
      if (kind === COMPARE_EXPORT_KIND && !isCompareExport(parsed)) {
        setStatus('Import failed: this challenges export is malformed. Check for a blank challenge note, id, or target, a duplicate challenge id, or a wrong field type.')
        return
      }
      if (!isCompareExport(parsed)) {
        setStatus(`Import failed: expected a stage 3 challenges export (kind "quirk-approach-comparison-challenges")${typeof kind === 'string' ? `, got kind "${kind}"` : ''}.`)
        return
      }
      const data = parsed as CompareExport
      if (data.slug !== slug) {
        setStatus(`Import failed: that export is for spec "${data.slug}", not "${slug}".`)
        return
      }
      const kept: Draft[] = []
      const moved: Draft[] = []
      for (const challenge of data.challenges) (currentHash(comparison, challenge) === challenge.targetHash ? kept : moved).push(challenge)
      const spec = readPayload().payload?.spec
      if (!spec) {
        setStatus('Import failed: the embedded review data is unavailable, so starred requirements cannot be checked against the spec.')
        return
      }
      const { kept: starred, dropped } = partitionStars(data.stars, comparison, spec)
      update((draft) => {
        const ids = new Set([...kept, ...moved].map((challenge) => challenge.id))
        draft.drafts = [...draft.drafts.filter((existing) => !ids.has(existing.id)), ...kept]
        draft.needsLook = [...draft.needsLook.filter((existing) => !ids.has(existing.id)), ...moved]
        draft.stars = [...new Set([...draft.stars, ...starred])]
        draft.droppedStars = [...new Set([...draft.droppedStars, ...dropped])]
      })
      setStatus(`Imported ${kept.length} challenge${kept.length === 1 ? '' : 's'} and ${starred.length} must-have${starred.length === 1 ? '' : 's'}${moved.length ? `; ${moved.length} need another look` : ''}.`)
    }).catch(() => setStatus('Import failed: could not read the selected file.'))
  }

  const removeDraft = (id: string) => update((draft) => { draft.drafts = draft.drafts.filter((item) => item.id !== id) })
  const discardLook = (id: string) => update((draft) => { draft.needsLook = draft.needsLook.filter((item) => item.id !== id) })
  const reaim = (item: Draft) => {
    const hash = currentHash(comparison, item)
    if (hash === null) return
    update((draft) => {
      draft.needsLook = draft.needsLook.filter((other) => other.id !== item.id)
      draft.drafts = [...draft.drafts, { ...item, targetHash: hash }]
    })
  }

  return (
    <Card padding={2}>
      <VStack gap={2}>
        <HStack gap={2} align="center" justify="between" wrap="wrap">
          <HStack gap={2} align="center" wrap="wrap">
            <Text type="label">Challenges</Text>
            <Token size="sm" color={state.drafts.length ? 'blue' : 'default'} label={`${state.drafts.length} draft${state.drafts.length === 1 ? '' : 's'}`} />
            <Token size="sm" color={state.needsLook.length ? 'orange' : 'default'} label={`${state.needsLook.length} need${state.needsLook.length === 1 ? 's' : ''} another look`} description="Drafts whose score or slice changed after a regeneration; they are never re-aimed without you." />
          </HStack>
          <HStack gap={1}>
            <Button variant="primary" label="Export" onClick={exportChallenges} />
            <Button label="Import" onClick={() => fileInputRef.current?.click()} />
            <input
              ref={fileInputRef}
              type="file"
              accept="application/json,.json"
              hidden
              onChange={(event) => {
                const file = event.currentTarget.files?.[0]
                if (file) importFile(file)
                event.currentTarget.value = ''
              }}
            />
          </HStack>
        </HStack>
        {state.needsLook.length > 0 ? (
          <Collapsible trigger={`Review ${state.needsLook.length} draft${state.needsLook.length === 1 ? '' : 's'} that need another look`} defaultIsOpen>
            <VStack gap={2}>
              {state.needsLook.map((item) => (
                <DraftRow key={item.id} draft={item} list="needsLook" update={update}>
                  <Button size="sm" label="Aim at the current score" isDisabled={currentHash(comparison, item) === null} onClick={() => reaim(item)} />
                  <Button size="sm" variant="secondary" label="Discard" onClick={() => discardLook(item.id)} />
                </DraftRow>
              ))}
            </VStack>
          </Collapsible>
        ) : null}
        {state.drafts.length > 0 ? (
          <Collapsible trigger={`Show ${state.drafts.length} draft${state.drafts.length === 1 ? '' : 's'}`} defaultIsOpen={false}>
            <VStack gap={2}>
              {state.drafts.map((item) => (
                <DraftRow key={item.id} draft={item} list="drafts" update={update}>
                  <Button size="sm" variant="secondary" label="Discard" onClick={() => removeDraft(item.id)} />
                </DraftRow>
              ))}
            </VStack>
          </Collapsible>
        ) : null}
        {status ? <Text type="supporting">{status}</Text> : null}
      </VStack>
    </Card>
  )
}
