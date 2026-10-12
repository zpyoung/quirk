import type { ReactNode } from 'react'
import { Heading } from '@astryxdesign/core/Heading'
import { Card, HStack, VStack } from '@astryxdesign/core/Layout'
import { Text } from '@astryxdesign/core/Text'
import { Token } from '@astryxdesign/core/Token'
import type { Approach, CompareViewProps } from '../../compare-types'
import { mrsFor } from '../../compare-state'

type Range = [number, number]
type RepoRow = { name: string; files: number | null; lines: Range | null; mrs: Range | null }

const fmt = ([low, high]: Range) => (low === high ? low.toLocaleString('en-US') : `${low.toLocaleString('en-US')}-${high.toLocaleString('en-US')}`)
const plural = (n: number, one: string, many: string) => (n === 1 ? one : many)
const add = (a: Range | null, b: Range): Range => (a ? [a[0] + b[0], a[1] + b[1]] : [b[0], b[1]])

/** Lines and MRs per repo summed over slices; a repo no slice gives lines for stays null so the page can say "not provided". */
function repoRows(approach: Approach): RepoRow[] {
  const names = approach.repos.map((repo) => repo.name)
  const rows = new Map<string, RepoRow>(approach.repos.map((repo) => [repo.name, { name: repo.name, files: repo.files, lines: null, mrs: null }]))
  for (const slice of approach.slices) {
    const mrs = mrsFor(slice)
    for (const [repo, lines] of Object.entries(slice.lines ?? {})) {
      if (!rows.has(repo)) {
        rows.set(repo, { name: repo, files: null, lines: null, mrs: null })
        names.push(repo)
      }
      const row = rows.get(repo)!
      row.lines = add(row.lines, lines)
      row.mrs = add(row.mrs, mrs[repo])
    }
  }
  return names.map((name) => rows.get(name)!)
}

function totals(rows: RepoRow[]): { lines: Range | null; mrs: Range | null } {
  let lines: Range | null = null
  let mrs: Range | null = null
  for (const row of rows) {
    if (row.lines) lines = add(lines, row.lines)
    if (row.mrs) mrs = add(mrs, row.mrs)
  }
  return { lines, mrs }
}

/** How many of an approach's slices carry line estimates; totals are partial sums when some do not. */
function estimateCoverage(approach: Approach): { estimated: number; all: number; partial: boolean } {
  const all = approach.slices.length
  const estimated = approach.slices.filter((slice) => slice.lines !== undefined).length
  return { estimated, all, partial: estimated < all }
}

/** A lines or MR range; a partial sum is a floor, so it reads as one and says how many slices it rests on. */
function rangeText(range: Range, unit: string, coverage: { estimated: number; all: number; partial: boolean }): string {
  return coverage.partial ? `≥ ${fmt(range)} ${unit} · ${coverage.estimated} of ${coverage.all} slices estimated` : fmt(range)
}

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <VStack gap={0}>
      <Text type="label" color="secondary">{label}</Text>
      {children}
    </VStack>
  )
}

const DEPLOY_LABEL = { stated: 'Deploy order stated', implied: 'Deploy order implied', 'not-stated': 'Deploy order not stated' } as const
const DEPLOY_COLOR = { stated: 'green', implied: 'yellow', 'not-stated': 'orange' } as const

function RepoBar({ row, maxLines, partial }: { row: RepoRow; maxLines: number; partial: boolean }) {
  if (!row.lines) return <Text type="supporting">not provided</Text>
  const low = (row.lines[0] / maxLines) * 100
  const high = (row.lines[1] / maxLines) * 100
  return (
    <div role="img" aria-label={`${partial ? 'at least ' : ''}${fmt(row.lines)} lines`} style={{ position: 'relative', height: 10, width: '100%', background: 'var(--color-background-muted)', borderRadius: 3 }}>
      <div style={{ position: 'absolute', inset: 0, width: `${high}%`, border: '1px dashed var(--color-border-blue)', borderRadius: 3, boxSizing: 'border-box' }} />
      <div style={{ position: 'absolute', inset: 0, width: `${low}%`, background: 'var(--color-background-blue)', border: '1px solid var(--color-border-blue)', borderRadius: 3, boxSizing: 'border-box' }} />
    </div>
  )
}

function BlastCard({ approach, maxLines }: { approach: Approach; maxLines: number }) {
  const rows = repoRows(approach)
  const { lines, mrs } = totals(rows)
  const coverage = estimateCoverage(approach)
  const { deploy } = approach
  return (
    <Card padding={2}>
      <VStack gap={3}>
        <Heading level={3}>{`Approach ${approach.id} · ${approach.title}`}</Heading>
        <HStack gap={4} wrap="wrap">
          <Fact label={coverage.partial ? 'MRs (partial)' : 'MRs in total'}>{mrs ? <Text type="label">{rangeText(mrs, plural(mrs[1], 'MR', 'MRs'), coverage)}</Text> : <Text type="supporting">not provided</Text>}</Fact>
          <Fact label={coverage.partial ? 'Lines (partial)' : 'Lines in total'}>{lines ? <Text type="label">{rangeText(lines, 'lines', coverage)}</Text> : <Text type="supporting">not provided</Text>}</Fact>
          <Fact label="Repos"><Text type="label">{String(rows.length)}</Text></Fact>
        </HStack>

        <VStack gap={1}>
          <Text type="label" color="secondary">Per repo</Text>
          {rows.length === 0 ? <Text type="supporting">not provided</Text> : null}
          {rows.map((row) => (
            <div key={row.name} style={{ display: 'grid', gridTemplateColumns: 'minmax(80px, 1fr) minmax(80px, 2fr) minmax(120px, 2fr)', gap: 12, alignItems: 'center' }}>
              <Text type="label">{row.name}</Text>
              <RepoBar row={row} maxLines={maxLines} partial={coverage.partial} />
              <Text type="supporting">
                {row.files === null ? 'files not provided' : `${row.files} ${row.files === 1 ? 'file' : 'files'}`}
                {row.lines && row.mrs ? ` · ${coverage.partial ? '≥ ' : ''}${fmt(row.lines)} lines · ${coverage.partial ? '≥ ' : ''}${fmt(row.mrs)} ${row.mrs[1] === 1 && row.mrs[0] === 1 ? 'MR' : 'MRs'}${coverage.partial ? ` · ${coverage.estimated} of ${coverage.all} slices estimated` : ''}` : ' · lines and MRs not provided'}
              </Text>
            </div>
          ))}
          <Text type="supporting">MRs count each slice per repo as ceil(lines / 500); slices are never merged.</Text>
        </VStack>

        <Fact label="Schema change">
          {approach.schemaChange ? <Text>{approach.schemaChange}</Text> : <Text type="supporting">not provided</Text>}
        </Fact>

        <Fact label="Hot paths touched">
          {approach.hotPaths.length ? (
            <HStack gap={1} wrap="wrap">{approach.hotPaths.map((path) => <Token key={path} size="sm" color="default" label={path} />)}</HStack>
          ) : (
            <Text type="supporting">none listed</Text>
          )}
        </Fact>

        <Fact label="Deploy order">
          <VStack gap={1}>
            <HStack><Token size="sm" color={DEPLOY_COLOR[deploy.status]} label={DEPLOY_LABEL[deploy.status]} /></HStack>
            {deploy.steps.length ? (
              <ol style={{ margin: 0, paddingInlineStart: 20 }}>{deploy.steps.map((step, index) => <li key={index}><Text>{step}</Text></li>)}</ol>
            ) : (
              <Text type="supporting">The spec doesn't give one.</Text>
            )}
          </VStack>
        </Fact>
      </VStack>
    </Card>
  )
}

/** What each approach touches, from the proponents' own line estimates, per slice per repo. */
export function BlastView(props: CompareViewProps) {
  const approaches = props.comparison.approaches.filter((approach) => props.approaches.includes(approach.id))
  const maxLines = Math.max(1, ...approaches.flatMap((approach) => repoRows(approach).map((row) => row.lines?.[1] ?? 0)))
  return (
    <VStack gap={3}>
      <VStack gap={1}>
        <Heading level={2}>Blast radius</Heading>
        <Text type="supporting">Line estimates come from each proponent. Per-repo bars share one scale: solid is the low estimate, dashed outline the high one.</Text>
      </VStack>
      {approaches.map((approach) => <BlastCard key={approach.id} approach={approach} maxLines={maxLines} />)}
    </VStack>
  )
}
