import { useMemo, useState } from 'react'
import type { CSSProperties } from 'react'
import { Button } from '@astryxdesign/core/Button'
import { Heading } from '@astryxdesign/core/Heading'
import { IconButton } from '@astryxdesign/core/IconButton'
import { Card, HStack, VStack } from '@astryxdesign/core/Layout'
import { Table, proportional, type TableColumn } from '@astryxdesign/core/Table'
import { Text } from '@astryxdesign/core/Text'
import { Token } from '@astryxdesign/core/Token'
import { Tooltip } from '@astryxdesign/core/Tooltip'
import { anchorMismatch, coverageCounts, defaultRows, pairAgrees, pointsFor, revisedRows, staleScore, visibleRequirements } from '../../compare-state'
import type { Approach, CompareViewProps, Score } from '../../compare-types'
import type { Requirement } from '../../spec-types'
import { CONDITION_LABEL } from '../../review-state'
import { findingsFor, latestHistory } from './score-drawer'
import { STATUS_META, STATUS_ORDER, StatusChip } from './status-chip'

const COUNT_WORD: Record<number, string> = { 2: 'both', 3: 'all three', 4: 'all four', 5: 'all five' }

const formatPoints = ([low, high]: [number, number]) => (low === high ? `${low} pts` : `${low}-${high} pts`)

function CountRow({ label, counts }: { label: string; counts: Record<(typeof STATUS_ORDER)[number], number> }) {
  return (
    <HStack gap={2} align="center" wrap="wrap">
      <Text type="supporting">{label}</Text>
      {STATUS_ORDER.map((status) => (
        <span key={status} role="img" aria-label={`${counts[status]} ${STATUS_META[status].label}`} title={STATUS_META[status].label} style={{ fontSize: 13, color: `var(--color-text-${STATUS_META[status].color})` }}>
          <span aria-hidden="true">{`${STATUS_META[status].glyph} ${counts[status]}`}</span>
        </span>
      ))}
    </HStack>
  )
}

function CoverageBar({ counts }: { counts: Record<(typeof STATUS_ORDER)[number], number> }) {
  const total = STATUS_ORDER.reduce((sum, status) => sum + counts[status], 0)
  const label = STATUS_ORDER.map((status) => `${counts[status]} ${STATUS_META[status].label}`).join(', ')
  return (
    <div role="img" aria-label={`Coverage: ${label}`} style={{ display: 'flex', height: 10, borderRadius: 5, overflow: 'hidden', background: 'var(--color-background-muted)', gap: 1 }}>
      {total > 0
        ? STATUS_ORDER.filter((status) => counts[status] > 0).map((status) => (
            <div key={status} title={`${STATUS_META[status].label}: ${counts[status]}`} style={{ flex: counts[status], background: `var(--color-border-${STATUS_META[status].color})` }} />
          ))
        : null}
    </div>
  )
}

function ApproachCard({ approach, props, mismatchedRepos }: { approach: Approach; props: CompareViewProps; mismatchedRepos: string[] }) {
  const { comparison, spec, state } = props
  const visible = visibleRequirements(spec, state)
  const visibleIds = new Set(visible.map((requirement) => requirement.id))
  const counts = coverageCounts(comparison, spec, state, approach.id)
  const all = { met: 0, 'met with workaround': 0, 'very hard': 0, 'not met': 0 }
  for (const status of STATUS_ORDER) all[status] = counts.min[status] + counts.increments[status]

  const v1Slices = approach.slices.filter((slice) => slice.band === 'v1').length
  const disputed = (comparison.findings ?? []).filter(
    (finding) => finding.type === 'disputes' && visibleIds.has(finding.requirementId) && (finding.approaches === 'all' || finding.approaches.includes(approach.id)),
  ).length

  const starred = state.stars.filter((id) => visibleIds.has(id))
  const missed = starred.filter((id) => {
    const status = comparison.scores[id]?.[approach.id]?.status
    return status !== undefined && status !== 'met'
  })
  const mustHaves =
    starred.length === 0
      ? 'Star requirements in the matrix to see how this approach meets your must-haves.'
      : missed.length > 0
        ? `Misses ${missed.length} of ${starred.length}: ${missed.join(', ')}`
        : `Meets all ${starred.length}`

  const checked = visible.filter((requirement) => comparison.scores[requirement.id]?.[approach.id]?.check).length
  const evidence = `${checked} of ${visible.length} scores checked · ${approach.restsOn?.length ?? 0} assumptions unverified`
  const lastRevision = state.lastExport?.approachRevisions[approach.id]
  const revisedSinceExport = lastRevision !== undefined && lastRevision !== approach.revision
  const anchors = approach.anchors.map((anchor) => `${anchor.repo}@${anchor.commit.slice(0, 7)}`).join(', ')

  return (
    <Card padding={3}>
      <VStack gap={3}>
        <VStack gap={0.5}>
          <Text type="label" color="secondary">{`Approach ${approach.id}`}</Text>
          <Heading level={3}>{approach.title}</Heading>
          <Text type="supporting">{`Read ${approach.readAt}${anchors ? ` · ${anchors}` : ''}`}</Text>
          {approach.anchors.some((anchor) => mismatchedRepos.includes(anchor.repo)) ? (
            <HStack>
              <Token size="sm" color="orange" label={`Anchored at a different commit than another approach: ${approach.anchors.filter((anchor) => mismatchedRepos.includes(anchor.repo)).map((anchor) => anchor.repo).join(', ')}`} />
            </HStack>
          ) : null}
          {revisedSinceExport ? (
            <HStack>
              <Token size="sm" color="orange" label="Revised since your last export" />
            </HStack>
          ) : null}
        </VStack>

        <VStack gap={1}>
          <CoverageBar counts={all} />
          <CountRow label="Minimum" counts={counts.min} />
          <CountRow label="Increments" counts={counts.increments} />
        </VStack>

        <HStack gap={3} wrap="wrap">
          <VStack gap={0.5}>
            <Text type="label" color="secondary">v1 effort</Text>
            <Text>{formatPoints(pointsFor(approach, 'v1'))}</Text>
          </VStack>
          <VStack gap={0.5}>
            <Text type="label" color="secondary">v1 slices</Text>
            <Text>{String(v1Slices)}</Text>
          </VStack>
          <VStack gap={0.5}>
            <Text type="label" color="secondary">Disputed findings</Text>
            <Text>{String(disputed)}</Text>
          </VStack>
        </HStack>

        <VStack gap={0.5}>
          <Text type="label" color="secondary">Your must-haves</Text>
          <Text>{mustHaves}</Text>
        </VStack>

        <VStack gap={0.5}>
          <Text type="label" color="secondary">Evidence</Text>
          <Text>{evidence}</Text>
        </VStack>
      </VStack>
    </Card>
  )
}

const CELL: CSSProperties = { padding: '8px 10px', verticalAlign: 'top', borderBottom: '1px solid var(--color-border)', minWidth: 170 }
const REVISED_TINT = 'color-mix(in srgb, var(--color-background-orange) 25%, transparent)'

function Glyph({ glyph, label }: { glyph: string; label: string }) {
  return (
    <Tooltip content={label}>
      <span role="img" aria-label={label} style={{ fontSize: 14, cursor: 'default' }}>{glyph}</span>
    </Tooltip>
  )
}

function ScoreCell({ requirement, approachId, props, revised }: { requirement: Requirement; approachId: string; props: CompareViewProps; revised: boolean }) {
  const { comparison, spec, itemHashes } = props
  const score: Score | undefined = comparison.scores[requirement.id]?.[approachId]
  if (!score) return <td style={CELL}><Text type="supporting">No score</Text></td>
  const findings = findingsFor(comparison, requirement.id, approachId)
  const stale = staleScore(score, spec, itemHashes, requirement.id).stale
  const outcome = latestHistory(score)?.outcome
  return (
    <td style={{ ...CELL, background: revised ? REVISED_TINT : undefined }}>
      <VStack gap={1} align="start">
        <HStack gap={1} align="center">
          <StatusChip status={score.status} qualifier={score.qualifier} size="sm" />
          {findings.some((finding) => finding.type === 'disputes') ? <Glyph glyph="⚑" label="A finding disputes this score" /> : null}
          {findings.some((finding) => finding.type === 'same score, different design') ? <Glyph glyph="≠" label="Same score, different design" /> : null}
          {score.check ? <Glyph glyph="·" label="Checked by the coordinator" /> : null}
        </HStack>
        {score.qualifier ? <Text type="supporting">{score.qualifier}</Text> : null}
        {stale ? <Token size="sm" color="yellow" label="Scored against older text" /> : null}
        {outcome ? <Token size="sm" color={outcome === 'revised' ? 'blue' : 'gray'} label={outcome === 'revised' ? 'Revised after challenge' : 'Held after challenge'} /> : null}
        {revised ? <Token size="sm" color="orange" label="Revised since your last export" /> : null}
      </VStack>
    </td>
  )
}

function Matrix({ props }: { props: CompareViewProps }) {
  const { comparison, spec, state, update, approaches, openRequirement } = props
  const [showAll, setShowAll] = useState(false)
  const visible = visibleRequirements(spec, state)
  const isPair = state.focus !== 'all' && approaches.length === 2

  const rowIds = useMemo(() => {
    if (showAll) return visible.map((requirement) => requirement.id)
    const rows = defaultRows(comparison, spec, state)
    if (!isPair) return rows
    return rows.filter((id) => !pairAgrees(comparison, id, approaches))
  }, [showAll, comparison, spec, state, approaches, isPair, visible])

  const revised = useMemo(() => Object.fromEntries(approaches.map((id) => [id, new Set(revisedRows(comparison, state, id))])), [comparison, state, approaches])

  const shown = visible.filter((requirement) => rowIds.includes(requirement.id))
  const hiddenCount = visible.length - (showAll ? visible.length : shown.length)
  const areas = [...new Set(shown.map((requirement) => requirement.area))]
  const outOfScope = spec.requirements.filter((requirement) => requirement.scope === 'out').length
  const hiddenLabel = isPair ? `+ ${hiddenCount} requirement${hiddenCount === 1 ? '' : 's'} where both agree` : `+ ${hiddenCount} requirement${hiddenCount === 1 ? '' : 's'} ${COUNT_WORD[approaches.length] ?? 'every approach'} meet`

  const toggleStar = (id: string) =>
    update((s) => {
      s.stars = s.stars.includes(id) ? s.stars.filter((star) => star !== id) : [...s.stars, id]
    })

  return (
    <VStack gap={2}>
      <div style={{ overflowX: 'auto', border: '1px solid var(--color-border)', borderRadius: 8, background: 'var(--color-background-surface)' }}>
        <table style={{ borderCollapse: 'separate', borderSpacing: 0, width: '100%', fontSize: 14, color: 'var(--color-text-primary)' }}>
          <thead>
            <tr>
              <th scope="col" style={{ ...CELL, position: 'sticky', left: 0, zIndex: 2, background: 'var(--color-background-surface)', textAlign: 'start', minWidth: 240 }}>Requirement</th>
              {approaches.map((id) => {
                const approach = comparison.approaches.find((candidate) => candidate.id === id)
                return (
                  <th key={id} scope="col" style={{ ...CELL, textAlign: 'start' }}>
                    <VStack gap={0.5}>
                      <Text type="label" color="secondary">{`Approach ${id}`}</Text>
                      <Text>{approach?.title ?? id}</Text>
                    </VStack>
                  </th>
                )
              })}
            </tr>
          </thead>
          <tbody>
            {areas.map((area) => (
              <AreaRows
                key={area}
                area={area}
                requirements={shown.filter((requirement) => requirement.area === area)}
                props={props}
                revised={revised}
                onToggleStar={toggleStar}
                onOpen={openRequirement}
              />
            ))}
            {shown.length === 0 ? (
              <tr>
                <td colSpan={approaches.length + 1} style={CELL}>
                  <Text type="supporting">No requirements to show in this view.</Text>
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
      <HStack gap={2} align="center" wrap="wrap">
        {showAll || hiddenCount > 0 ? (
          <Button variant="secondary" size="sm" label={showAll ? 'Show only the rows that differ' : hiddenLabel} aria-expanded={showAll} onClick={() => setShowAll((value) => !value)} />
        ) : null}
        {outOfScope > 0 ? <Text type="supporting">{`${outOfScope} out-of-scope requirement${outOfScope === 1 ? '' : 's'} not scored`}</Text> : null}
      </HStack>
    </VStack>
  )
}

function AreaRows({
  area,
  requirements,
  props,
  revised,
  onToggleStar,
  onOpen,
}: {
  area: string
  requirements: Requirement[]
  props: CompareViewProps
  revised: Record<string, Set<string>>
  onToggleStar: (id: string) => void
  onOpen: (id: string) => void
}) {
  const { state, approaches } = props
  return (
    <>
      <tr>
        <th
          scope="colgroup"
          colSpan={approaches.length + 1}
          style={{ ...CELL, position: 'sticky', left: 0, textAlign: 'start', background: 'var(--color-background-muted)', fontWeight: 600 }}
        >
          {area}
        </th>
      </tr>
      {requirements.map((requirement) => {
        const starred = state.stars.includes(requirement.id)
        return (
          <tr key={requirement.id} onClick={() => onOpen(requirement.id)} style={{ cursor: 'pointer' }}>
            <th scope="row" style={{ ...CELL, position: 'sticky', left: 0, zIndex: 1, background: 'var(--color-background-surface)', textAlign: 'start', fontWeight: 400 }}>
              <HStack gap={1} align="start" wrap="nowrap">
                <span onClick={(event) => event.stopPropagation()}>
                  <IconButton
                    variant="ghost"
                    size="sm"
                    label={starred ? `Remove ${requirement.id} from your must-haves` : `Mark ${requirement.id} as a must-have`}
                    aria-pressed={starred}
                    icon={<span aria-hidden="true">{starred ? '★' : '☆'}</span>}
                    onClick={() => onToggleStar(requirement.id)}
                  />
                </span>
                <VStack gap={0.5}>
                  <HStack gap={1} align="center" wrap="wrap">
                    <button
                      type="button"
                      onClick={(event) => {
                        event.stopPropagation()
                        onOpen(requirement.id)
                      }}
                      style={{ all: 'unset', cursor: 'pointer', fontWeight: 600, textDecoration: 'underline' }}
                    >
                      {requirement.id}
                    </button>
                    {requirement.condition ? <Token size="sm" color="blue" label="Conditional" description={CONDITION_LABEL[requirement.condition]} /> : null}
                  </HStack>
                  <Text>{requirement.summary}</Text>
                  <Text type="supporting">{requirement.area}</Text>
                </VStack>
              </HStack>
            </th>
            {approaches.map((id) => (
              <ScoreCell key={id} requirement={requirement} approachId={id} props={props} revised={revised[id]?.has(requirement.id) ?? false} />
            ))}
          </tr>
        )
      })}
    </>
  )
}

type ChoiceRow = { id: string; question: string } & Record<string, string>

function Choices({ props }: { props: CompareViewProps }) {
  const { comparison, approaches } = props
  const choices = comparison.choices ?? []
  if (choices.length === 0) return null
  const isPair = approaches.length === 2
  const rows: ChoiceRow[] = choices
    .filter((choice) => !isPair || (choice.answers[approaches[0]!] ?? '').trim() !== (choice.answers[approaches[1]!] ?? '').trim())
    .map((choice, index) => ({ id: `choice-${index}`, question: choice.question, ...Object.fromEntries(approaches.map((id) => [id, choice.answers[id] ?? '—'])) }))
  const columns: TableColumn<ChoiceRow>[] = [
    { key: 'question', header: 'Question', width: proportional(2), renderCell: (row) => <Text type="label">{row.question}</Text> },
    ...approaches.map((id): TableColumn<ChoiceRow> => ({
      key: id,
      header: `Approach ${id}`,
      width: proportional(2),
      renderCell: (row) => <Text>{row[id] ?? '—'}</Text>,
    })),
  ]
  return (
    <VStack gap={2}>
      <Heading level={3}>{`Same question, ${approaches.length} answers`}</Heading>
      {rows.length > 0 ? <Table data={rows} columns={columns} idKey="id" verticalAlign="top" dividers="rows" /> : <Text type="supporting">These two approaches give the same answer to every question.</Text>}
    </VStack>
  )
}

/** Stage-3 Overview tab: one card per focused approach, the requirement-by-approach matrix, and the design-choices table. Rows open the score drawer through `openRequirement`. */
export function OverviewView(props: CompareViewProps) {
  const { comparison, approaches } = props
  const mismatch = anchorMismatch(comparison)
  const mismatchedRepos = Object.keys(mismatch).filter((repo) => mismatch[repo])
  const focused = approaches.map((id) => comparison.approaches.find((approach) => approach.id === id)).filter((approach): approach is Approach => approach !== undefined)
  return (
    <VStack gap={4}>
      <VStack gap={1}>
        <Heading level={2}>Overview</Heading>
        <Text type="supporting" as="p">
          Each approach's scores against the signed requirements. Scores are the proponents' own unless marked checked.
        </Text>
      </VStack>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 16 }}>
        {focused.map((approach) => (
          <ApproachCard key={approach.id} approach={approach} props={props} mismatchedRepos={mismatchedRepos} />
        ))}
      </div>
      <VStack gap={2}>
        <Heading level={3}>Requirements by approach</Heading>
        <Matrix props={props} />
      </VStack>
      <Choices props={props} />
    </VStack>
  )
}
