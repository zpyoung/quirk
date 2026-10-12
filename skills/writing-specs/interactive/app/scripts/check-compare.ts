import { readdirSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import comparisonFixture from '../../../../../tests/fixtures/interactive/v2/compare/comparison.json'
import logicFixture from '../../../../../tests/fixtures/interactive/v2/compare/logic.json'
import expectedHashes from '../../../../../tests/fixtures/interactive/v2/compare/expected-hashes.json'
import {
  POINT_MAP,
  allHistoryCounts,
  anchorMismatch,
  canonicalJson,
  coverageCounts,
  createCompareExport,
  defaultRows,
  focusApproaches,
  guidanceNotes,
  isCompareExport,
  isComparison,
  loadCompareState,
  mrsFor,
  pointsFor,
  revisedRows,
  saveCompareState,
  sha256Hex,
  staleScore,
  targetHash,
  visibleRequirements,
} from '../src/compare-state'
import type { CompareState, Comparison, Draft, ScoreStatus } from '../src/compare-types'
import type { LogicSpec } from '../src/spec-types'

const failures: string[] = []
function check(name: string, ok: boolean, detail = ''): void {
  if (!ok) failures.push(detail ? `${name}: ${detail}` : name)
}
function equal(name: string, actual: unknown, expected: unknown): void {
  const a = JSON.stringify(actual)
  const e = JSON.stringify(expected)
  if (a !== e) failures.push(`${name}: expected ${e}, got ${a}`)
}

const spec = logicFixture as unknown as LogicSpec
const accepted = isComparison(comparisonFixture, spec)
if (!accepted.ok) {
  console.error(`compare-check failed:\n- fixture comparison.json rejected at ${accepted.pointer}: ${accepted.message}`)
  process.exit(1)
}
const comparison: Comparison = accepted.value
check('isComparison without a spec accepts the fixture', isComparison(comparisonFixture).ok)

// invalid fixtures: each must be rejected at a pointer under its expected prefix
const invalidDir = fileURLToPath(new URL('../../../../../tests/fixtures/interactive/v2/compare/invalid/', import.meta.url))
const expectedPointers = JSON.parse(readFileSync(`${invalidDir}expected.json`, 'utf8')) as Record<string, string>
const invalidFiles = readdirSync(invalidDir).filter((name) => name.endsWith('.json') && name !== 'expected.json').sort()
equal('invalid fixture list matches expected.json', invalidFiles, Object.keys(expectedPointers).sort())
for (const name of invalidFiles) {
  const result = isComparison(JSON.parse(readFileSync(`${invalidDir}${name}`, 'utf8')), spec)
  if (result.ok) {
    failures.push(`invalid/${name}: accepted, expected rejection at ${expectedPointers[name]}`)
    continue
  }
  const prefix = expectedPointers[name] ?? ''
  check(`invalid/${name} pointer`, result.pointer.startsWith(prefix), `pointer ${result.pointer} does not start with ${prefix} (${result.message})`)
}
for (const junk of [null, 3, 'x', [], {}]) check(`isComparison rejects ${JSON.stringify(junk)}`, !isComparison(junk, spec).ok)

// hashing: parity with the Python fixtures
equal('sha256 of "abc"', sha256Hex('abc'), 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad')
equal('sha256 of empty string', sha256Hex(''), 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855')
equal('canonicalJson', canonicalJson({ b: [1, true, null], a: 'naïve "q"\n', c: {} }), '{"a":"naïve \\"q\\"\\n","b":[1,true,null],"c":{}}')
equal('comparisonId', sha256Hex(canonicalJson(comparison)).slice(0, 12), expectedHashes.comparisonId)
const targets = expectedHashes.targets as Record<string, string>
let hashed = 0
for (const [requirementId, row] of Object.entries(comparison.scores)) {
  for (const [approachId, score] of Object.entries(row)) {
    equal(`targetHash score|${requirementId}|${approachId}`, targetHash(score, 'score'), targets[`score|${requirementId}|${approachId}`])
    hashed += 1
  }
}
for (const approach of comparison.approaches) {
  for (const slice of approach.slices) {
    equal(`targetHash slice|${approach.id}|${slice.id}`, targetHash(slice, 'slice'), targets[`slice|${approach.id}|${slice.id}`])
    hashed += 1
  }
}
equal('every expected target hash was checked', hashed, Object.keys(targets).length)

// derived values, computed by hand from the fixture
equal('POINT_MAP', POINT_MAP, { S: [2, 2], 'S-M': [2, 3], M: [3, 3], 'M-L': [3, 5], L: [5, 5], 'L-XL': [5, 8], XL: [8, 8] })
const fresh = (overrides: Partial<CompareState> = {}): CompareState => ({
  comparisonId: 'cid', drafts: [], needsLook: [], stars: [], focus: 'all', includeConditional: true, droppedStars: [], lastExport: null, ...overrides,
})
const counts = (met: number, workaround: number, hard: number, notMet: number): Record<ScoreStatus, number> => ({
  met, 'met with workaround': workaround, 'very hard': hard, 'not met': notMet,
})
const approach = (id: string) => comparison.approaches.find((a) => a.id === id)!
const COVERAGE_ALL = {
  A: { min: counts(2, 0, 0, 0), increments: counts(2, 0, 0, 0), notFullyMet: [] as string[] },
  B: { min: counts(2, 0, 0, 0), increments: counts(1, 1, 0, 0), notFullyMet: ['REQ-02'] },
  C: { min: counts(2, 0, 0, 0), increments: counts(0, 0, 1, 1), notFullyMet: ['REQ-02', 'REQ-03'] },
}
const COVERAGE_NO_CONDITIONAL = {
  A: { min: counts(2, 0, 0, 0), increments: counts(1, 0, 0, 0), notFullyMet: [] as string[] },
  B: { min: counts(2, 0, 0, 0), increments: counts(0, 1, 0, 0), notFullyMet: ['REQ-02'] },
  C: { min: counts(2, 0, 0, 0), increments: counts(0, 0, 1, 0), notFullyMet: ['REQ-02'] },
}
for (const id of ['A', 'B', 'C'] as const) {
  equal(`coverageCounts ${id}`, coverageCounts(comparison, spec, fresh(), id), COVERAGE_ALL[id])
  equal(`coverageCounts ${id} without conditional`, coverageCounts(comparison, spec, fresh({ includeConditional: false }), id), COVERAGE_NO_CONDITIONAL[id])
}
const POINTS = {
  A: { v1: [10, 11], 'fast-follow': [2, 2], optional: [3, 5] },
  B: { v1: [8, 10], 'fast-follow': [2, 3], optional: [13, 16] },
  C: { v1: [10, 14], 'fast-follow': [3, 5], optional: [8, 8] },
} as const
for (const id of ['A', 'B', 'C'] as const) {
  for (const band of ['v1', 'fast-follow', 'optional'] as const) equal(`pointsFor ${id} ${band}`, pointsFor(approach(id), band), POINTS[id][band])
}
const MRS: Record<string, Record<string, [number, number]>> = {
  'A-1': { core: [1, 2] }, 'A-2': {}, 'A-3': { core: [1, 1], tools: [1, 1] },
  'B-1': { core: [1, 1] }, 'B-4': { core: [1, 1] },
  'C-1': { core: [2, 4], tools: [1, 1] }, 'C-2': {},
}
for (const id of ['A', 'B', 'C']) {
  for (const slice of approach(id).slices) if (slice.id in MRS) equal(`mrsFor ${slice.id}`, mrsFor(slice), MRS[slice.id])
}
equal('mrsFor rounds up each end', mrsFor({ ...approach('A').slices[0]!, lines: { core: [500, 501] } }), { core: [1, 2] })

// views
equal('visibleRequirements', visibleRequirements(spec, fresh()).map((r) => r.id), ['REQ-01', 'REQ-02', 'REQ-03', 'REQ-04'])
equal('visibleRequirements without conditional', visibleRequirements(spec, fresh({ includeConditional: false })).map((r) => r.id), ['REQ-01', 'REQ-02', 'REQ-04'])
equal('focusApproaches all', focusApproaches(comparison, fresh()), ['A', 'B', 'C'])
equal('focusApproaches pair', focusApproaches(comparison, fresh({ focus: 'AC' })), ['A', 'C'])
equal('focusApproaches unknown pair falls back to all', focusApproaches(comparison, fresh({ focus: 'AZ' })), ['A', 'B', 'C'])
equal('defaultRows all', defaultRows(comparison, spec, fresh()), ['REQ-01', 'REQ-02', 'REQ-03'])
equal('defaultRows pair A,B', defaultRows(comparison, spec, fresh({ focus: 'AB' })), ['REQ-01', 'REQ-02'])
equal('defaultRows pair A,C without conditional', defaultRows(comparison, spec, fresh({ focus: 'AC', includeConditional: false })), ['REQ-01', 'REQ-02'])

const itemHashes: Record<string, string> = { 'REQ-01': 'h1' }
const baseScore = comparison.scores['REQ-01']!.A!
equal('staleScore fresh', staleScore({ ...baseScore, requirementHash: 'h1' }, spec, itemHashes, 'REQ-01').stale, false)
const stale = staleScore({ ...baseScore, requirementHash: 'old', requirementText: 'Old text.' }, spec, itemHashes, 'REQ-01')
equal('staleScore stale', [stale.stale, stale.oldText, stale.newText], [true, 'Old text.', spec.requirements.find((r) => r.id === 'REQ-01')!.text])

const exported: Record<string, string> = {}
for (const [requirementId, row] of Object.entries(comparison.scores)) for (const [approachId, score] of Object.entries(row)) exported[`${requirementId}|${approachId}`] = targetHash(score, 'score')
const changed = structuredClone(comparison)
changed.scores['REQ-02']!.B!.note = 'A different note.'
changed.scores['REQ-04']!.A!.note = 'A different note.'
const withExport = fresh({ lastExport: { at: 'x', approachRevisions: {}, scoreHashes: exported } })
equal('revisedRows detects a changed score', revisedRows(changed, withExport, 'B'), ['REQ-02'])
equal('revisedRows skips a score that gained history', revisedRows(changed, withExport, 'A'), [])
const historyExport = fresh({ lastExport: { at: 'x', approachRevisions: {}, scoreHashes: exported, historyCounts: allHistoryCounts(comparison) } })
const aged = structuredClone(comparison)
const olderHistory = aged.scores['REQ-04']!.A!.history ?? []
check('fixture REQ-04|A carries older history', olderHistory.length > 0, 'fixture REQ-04|A has no history')
aged.scores['REQ-04']!.A!.note = 'An unexplained edit.'
equal('revisedRows flags a changed score with older history and unchanged length', revisedRows(aged, historyExport, 'A'), ['REQ-04'])
const answered = structuredClone(aged)
answered.scores['REQ-04']!.A!.history = [...olderHistory, olderHistory[olderHistory.length - 1]!]
equal('revisedRows skips a changed score whose history grew', revisedRows(answered, historyExport, 'A'), [])
equal('revisedRows reads a missing historyCounts entry as 0', revisedRows(aged, withExport, 'A'), [])
equal('revisedRows without a prior export', revisedRows(changed, fresh(), 'B'), [])
equal('anchorMismatch', anchorMismatch(comparison), { core: true, tools: false })

const pickC = structuredClone(comparison)
pickC.guidance!.recommendation.approachId = 'C'
const guided = guidanceNotes(pickC, spec, fresh({ stars: ['REQ-02'], focus: 'AB', includeConditional: false }))
check('guidanceNotes covers starred miss, left-out conditional and pair focus', guided.length === 3, JSON.stringify(guided))
equal('guidanceNotes quiet when the pick meets the stars', guidanceNotes(comparison, spec, fresh({ stars: ['REQ-02'] })), [])
equal('guidanceNotes quiet by default', guidanceNotes(comparison, spec, fresh()), [])

// export and state round trip
const draft: Draft = { id: 'd1', target: { type: 'score', requirementId: 'REQ-02', approachId: 'B' }, note: 'Check this.', want: 'met', targetHash: targets['score|REQ-02|B']! }
const out = createCompareExport('compare', 'rid', 'cid', comparison, fresh({ drafts: [draft], stars: ['REQ-01'] }))
check('createCompareExport shape', isCompareExport(out), JSON.stringify(out))
equal('createCompareExport content', [out.kind, out.schemaVersion, out.slug, out.renderId, out.comparisonId, out.challenges, out.stars, out.approachRevisions],
  ['quirk-approach-comparison-challenges', 1, 'compare', 'rid', 'cid', [draft], ['REQ-01'], { A: 'A-r2', B: 'B-r1', C: 'C-r1' }])
const goodExport = JSON.parse(readFileSync(`${invalidDir}../exports/valid.json`, 'utf8'))
check('isCompareExport accepts exports/valid.json', isCompareExport(goodExport))
check('isCompareExport rejects exports/bad-shape.json', !isCompareExport(JSON.parse(readFileSync(`${invalidDir}../exports/bad-shape.json`, 'utf8'))))
check('isCompareExport rejects a score want on a slice target', !isCompareExport({ ...out, challenges: [{ ...draft, target: { type: 'slice', approachId: 'A', sliceId: 'A-1' } }] }))
check('isCompareExport rejects a non-ISO exportedAt', !isCompareExport({ ...out, exportedAt: 'yesterday' }))
check('isCompareExport accepts an ISO exportedAt with offset', isCompareExport({ ...out, exportedAt: '2026-10-12T09:30:00+02:00' }))
check('isCompareExport rejects an empty note', !isCompareExport({ ...out, challenges: [{ ...draft, note: '' }] }))

const store = new Map<string, string>()
Object.defineProperty(globalThis, 'localStorage', {
  configurable: true,
  value: { getItem: (k: string) => store.get(k) ?? null, setItem: (k: string, v: string) => void store.set(k, v), removeItem: (k: string) => void store.delete(k) },
})
const staleDraft: Draft = { ...draft, id: 'd2', target: { type: 'score', requirementId: 'REQ-01', approachId: 'A' }, targetHash: 'stale-hash' }
const goodDraft: Draft = { ...draft, id: 'd3', target: { type: 'slice', approachId: 'A', sliceId: 'A-1' }, want: 'L-XL', targetHash: targets['slice|A|A-1']! }
check('saveCompareState succeeds', saveCompareState('compare', fresh({ comparisonId: 'old', drafts: [draft, staleDraft, goodDraft], stars: ['REQ-01', 'REQ-05', 'REQ-99'], focus: 'AB' })))
check('storage key', store.has('quirk-compare:compare'))
const loaded = loadCompareState('compare', comparison, 'new')
check('loadCompareState storageOk', loaded.storageOk)
equal('carry-over keeps unchanged drafts', loaded.state.drafts.map((d) => d.id), ['d1', 'd3'])
equal('carry-over moves changed drafts to needsLook', loaded.state.needsLook.map((d) => d.id), ['d2'])
equal('carry-over drops stars no longer in scope', [loaded.state.stars, loaded.state.droppedStars, loaded.state.comparisonId, loaded.state.focus], [['REQ-01'], ['REQ-05', 'REQ-99'], 'new', 'AB'])
equal('same comparisonId loads unchanged', loadCompareState('compare', comparison, 'old').state.drafts.length, 3)
store.set('quirk-compare:compare', '{not json')
check('corrupt storage yields a fresh state', loadCompareState('compare', comparison, 'new').state.drafts.length === 0)
equal('missing storage yields a fresh state', loadCompareState('other', comparison, 'new').state, fresh({ comparisonId: 'new' }))

if (failures.length) {
  console.error(`compare-check failed (${failures.length}):\n${failures.map((f) => `- ${f}`).join('\n')}`)
  process.exit(1)
}
console.log(`compare-check passed: fixture accepted, ${invalidFiles.length} invalid fixtures rejected, ${hashed} target hashes and comparison id match.`)
