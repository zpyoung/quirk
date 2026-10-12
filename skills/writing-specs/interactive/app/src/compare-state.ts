import type {
  Approach,
  Band,
  CompareExport,
  CompareState,
  Comparison,
  Draft,
  Score,
  ScoreStatus,
  SizeLabel,
  Slice,
} from './compare-types'
import type { LogicSpec, Requirement } from './spec-types'

export const COMPARISON_KIND = 'quirk-approach-comparison'
export const COMPARE_EXPORT_KIND = 'quirk-approach-comparison-challenges'

const SCORE_STATUSES: readonly ScoreStatus[] = ['met', 'met with workaround', 'very hard', 'not met']
const BANDS: readonly Band[] = ['v1', 'fast-follow', 'optional']
const TAB_KEYS = ['overview', 'approaches', 'effort', 'blast', 'tradeoffs']
const MR_LINES = 500

/** Story points `[low, high]` per slice size label; mirrors the Python `POINT_MAP`. */
export const POINT_MAP: Record<SizeLabel, [number, number]> = {
  S: [2, 2],
  'S-M': [2, 3],
  M: [3, 3],
  'M-L': [3, 5],
  L: [5, 5],
  'L-XL': [5, 8],
  XL: [8, 8],
}

const isLineCount = (value: unknown): boolean => typeof value === 'number' && Number.isSafeInteger(value) && value >= 0
const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value)
const isScoreStatus = (value: unknown): value is ScoreStatus => typeof value === 'string' && (SCORE_STATUSES as readonly string[]).includes(value)
const isSizeLabel = (value: unknown): value is SizeLabel => typeof value === 'string' && Object.prototype.hasOwnProperty.call(POINT_MAP, value)

// ---------------------------------------------------------------------------
// Hashing

/** JSON with sorted keys and compact separators, byte-identical to Python `json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=False)` for the types the comparison holds. */
export function canonicalJson(value: unknown): string {
  if (value === null) return 'null'
  if (Array.isArray(value)) return `[${value.map((item) => canonicalJson(item === undefined ? null : item)).join(',')}]`
  if (isRecord(value)) {
    const parts: string[] = []
    for (const key of Object.keys(value).sort()) {
      const item = value[key]
      if (item !== undefined) parts.push(`${JSON.stringify(key)}:${canonicalJson(item)}`)
    }
    return `{${parts.join(',')}}`
  }
  return JSON.stringify(value)
}

const SHA256_K = new Uint32Array([
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
])

/** Synchronous SHA-256 of the UTF-8 encoding of `text`, as lowercase hex. `crypto.subtle` is async and unreliable on `file://`, which is where the page runs. */
export function sha256Hex(text: string): string {
  const bytes = new TextEncoder().encode(text)
  const paddedLength = (((bytes.length + 8) >> 6) + 1) << 6
  const padded = new Uint8Array(paddedLength)
  padded.set(bytes)
  padded[bytes.length] = 0x80
  const view = new DataView(padded.buffer)
  view.setUint32(paddedLength - 8, Math.floor((bytes.length * 8) / 0x100000000))
  view.setUint32(paddedLength - 4, (bytes.length * 8) >>> 0)

  const h = new Uint32Array([0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19])
  const w = new Uint32Array(64)
  const rotr = (x: number, n: number) => (x >>> n) | (x << (32 - n))
  for (let offset = 0; offset < paddedLength; offset += 64) {
    for (let i = 0; i < 16; i += 1) w[i] = view.getUint32(offset + i * 4)
    for (let i = 16; i < 64; i += 1) {
      const w15 = w[i - 15]!
      const w2 = w[i - 2]!
      const s0 = rotr(w15, 7) ^ rotr(w15, 18) ^ (w15 >>> 3)
      const s1 = rotr(w2, 17) ^ rotr(w2, 19) ^ (w2 >>> 10)
      w[i] = (w[i - 16]! + s0 + w[i - 7]! + s1) >>> 0
    }
    let [a, b, c, d, e, f, g, hh] = [h[0]!, h[1]!, h[2]!, h[3]!, h[4]!, h[5]!, h[6]!, h[7]!]
    for (let i = 0; i < 64; i += 1) {
      const t1 = (hh + (rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25)) + ((e & f) ^ (~e & g)) + SHA256_K[i]! + w[i]!) >>> 0
      const t2 = ((rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22)) + ((a & b) ^ (a & c) ^ (b & c))) >>> 0
      hh = g
      g = f
      f = e
      e = (d + t1) >>> 0
      d = c
      c = b
      b = a
      a = (t1 + t2) >>> 0
    }
    h[0] = (h[0]! + a) >>> 0
    h[1] = (h[1]! + b) >>> 0
    h[2] = (h[2]! + c) >>> 0
    h[3] = (h[3]! + d) >>> 0
    h[4] = (h[4]! + e) >>> 0
    h[5] = (h[5]! + f) >>> 0
    h[6] = (h[6]! + g) >>> 0
    h[7] = (h[7]! + hh) >>> 0
  }
  return Array.from(h, (word) => word.toString(16).padStart(8, '0')).join('')
}

const SCORE_HASHED_FIELDS = ['status', 'qualifier', 'wording', 'note', 'citations', 'requirementHash'] as const
const SLICE_HASHED_FIELDS = ['name', 'size', 'band', 'lines'] as const

/** First 12 hex of the SHA-256 of the content a reviewer argues with; fields absent from `obj` are omitted, matching the Python side. */
export function targetHash(obj: Score | Slice, kind: 'score' | 'slice'): string {
  const fields: readonly string[] = kind === 'score' ? SCORE_HASHED_FIELDS : SLICE_HASHED_FIELDS
  const source = obj as unknown as Record<string, unknown>
  const picked: Record<string, unknown> = {}
  for (const field of fields) if (source[field] !== undefined) picked[field] = source[field]
  return sha256Hex(canonicalJson(picked)).slice(0, 12)
}

// ---------------------------------------------------------------------------
// Validation

export type ComparisonResult = { ok: true; value: Comparison } | { ok: false; pointer: string; message: string }

class Invalid extends Error {
  constructor(readonly pointer: string, message: string) {
    super(message)
  }
}

const fail = (pointer: string, message: string): never => {
  throw new Invalid(pointer, message)
}

const str = (value: unknown, pointer: string): string => (typeof value === 'string' ? value : fail(pointer, 'must be a string'))
const int = (value: unknown, pointer: string): number => (typeof value === 'number' && Number.isInteger(value) ? value : fail(pointer, 'must be an integer'))
const bool = (value: unknown, pointer: string): boolean => (typeof value === 'boolean' ? value : fail(pointer, 'must be a boolean'))
const obj = (value: unknown, pointer: string): Record<string, unknown> => (isRecord(value) ? value : fail(pointer, 'must be an object'))
const arr = (value: unknown, pointer: string): unknown[] => (Array.isArray(value) ? value : fail(pointer, 'must be an array'))
const oneOf = (value: unknown, allowed: readonly string[], pointer: string): string =>
  typeof value === 'string' && allowed.includes(value) ? value : fail(pointer, `must be one of ${allowed.join(', ')}`)
const strings = (value: unknown, pointer: string): void => arr(value, pointer).forEach((item, i) => str(item, `${pointer}/${i}`))
const required = (record: Record<string, unknown>, key: string, pointer: string): unknown =>
  key in record ? record[key] : fail(`${pointer}/${key}`, `is required`)
const optional = (record: Record<string, unknown>, key: string, check: (value: unknown, pointer: string) => void, pointer: string): void => {
  if (record[key] !== undefined) check(record[key], `${pointer}/${key}`)
}

function checkSlice(value: unknown, pointer: string): void {
  const slice = obj(value, pointer)
  str(required(slice, 'id', pointer), `${pointer}/id`)
  str(required(slice, 'name', pointer), `${pointer}/name`)
  const size = required(slice, 'size', pointer)
  if (!isSizeLabel(size)) fail(pointer, `size must be one of ${Object.keys(POINT_MAP).join(', ')}`)
  oneOf(required(slice, 'band', pointer), BANDS, `${pointer}/band`)
  str(required(slice, 'area', pointer), `${pointer}/area`)
  str(required(slice, 'risk', pointer), `${pointer}/risk`)
  optional(slice, 'riskHeadline', str, pointer)
  optional(slice, 'lines', (lines, linesPointer) => {
    for (const [repo, range] of Object.entries(obj(lines, linesPointer))) {
      const spanPointer = `${linesPointer}/${repo.replace(/~/g, '~0').replace(/\//g, '~1')}`
      const pair = arr(range, spanPointer)
      const [lo, hi] = pair
      if (pair.length !== 2 || !isLineCount(lo) || !isLineCount(hi)) fail(spanPointer, 'expected [lo, hi] with integers from 0 to 2^53-1')
      else if ((lo as number) > (hi as number)) fail(spanPointer, 'lo must not exceed hi')
    }
  }, pointer)
}

function checkScore(value: unknown, pointer: string): void {
  const score = obj(value, pointer)
  if (!isScoreStatus(required(score, 'status', pointer))) fail(`${pointer}/status`, `must be one of ${SCORE_STATUSES.join(', ')}`)
  optional(score, 'qualifier', str, pointer)
  for (const key of ['wording', 'note', 'requirementHash', 'requirementText']) str(required(score, key, pointer), `${pointer}/${key}`)
  strings(required(score, 'citations', pointer), `${pointer}/citations`)
  optional(score, 'check', str, pointer)
  optional(score, 'history', (history, historyPointer) => {
    arr(history, historyPointer).forEach((entry, i) => {
      const at = `${historyPointer}/${i}`
      const record = obj(entry, at)
      const previous = obj(required(record, 'previous', at), `${at}/previous`)
      if (!isScoreStatus(required(previous, 'status', `${at}/previous`))) fail(`${at}/previous/status`, `must be one of ${SCORE_STATUSES.join(', ')}`)
      optional(previous, 'qualifier', str, `${at}/previous`)
      str(required(record, 'challenge', at), `${at}/challenge`)
      str(required(record, 'reply', at), `${at}/reply`)
      oneOf(required(record, 'outcome', at), ['revised', 'held'], `${at}/outcome`)
    })
  }, pointer)
}

function checkFlow(approach: Record<string, unknown>, flowStages: string[], pointer: string): void {
  optional(approach, 'flow', (flow, flowPointer) => {
    const seen = new Set<string>()
    arr(flow, flowPointer).forEach((entry, i) => {
      const at = `${flowPointer}/${i}`
      const box = obj(entry, at)
      const stage = str(required(box, 'stage', at), `${at}/stage`)
      const lane = str(required(box, 'lane', at), `${at}/lane`)
      str(required(box, 'text', at), `${at}/text`)
      oneOf(required(box, 'kind', at), ['new', 'changed', 'reused'], `${at}/kind`)
      optional(box, 'focal', bool, at)
      if (!flowStages.includes(stage)) fail(at, `stage "${stage}" is not in flowStages`)
      const cell = JSON.stringify([lane, stage])
      if (seen.has(cell)) fail(flowPointer, `two boxes share lane "${lane}" and stage "${stage}"`)
      seen.add(cell)
    })
  }, pointer)
}

function checkSequence(approach: Record<string, unknown>, pointer: string): void {
  optional(approach, 'sequence', (sequence, at) => {
    const record = obj(sequence, at)
    const participants = arr(required(record, 'participants', at), `${at}/participants`)
    strings(participants, `${at}/participants`)
    if (participants.length > 5) fail(`${at}/participants`, 'at most 5 participants')
    const messages = arr(required(record, 'messages', at), `${at}/messages`)
    if (messages.length > 12) fail(`${at}/messages`, 'at most 12 messages')
    messages.forEach((entry, i) => {
      const messageAt = `${at}/messages/${i}`
      const message = obj(entry, messageAt)
      for (const end of ['from', 'to']) {
        const name = str(required(message, end, messageAt), `${messageAt}/${end}`)
        if (!participants.includes(name)) fail(messageAt, `${end} "${name}" is not a participant`)
      }
      str(required(message, 'label', messageAt), `${messageAt}/label`)
      oneOf(required(message, 'kind', messageAt), ['call', 'return', 'async', 'focal'], `${messageAt}/kind`)
    })
  }, pointer)
}

function checkSchema(approach: Record<string, unknown>, pointer: string): void {
  optional(approach, 'schema', (schema, at) => {
    const record = obj(schema, at)
    const tables = arr(required(record, 'tables', at), `${at}/tables`)
    if (tables.length > 5) fail(at, 'at most 5 tables')
    const columnsByTable = new Map<string, string[]>()
    tables.forEach((entry, i) => {
      const tableAt = `${at}/tables/${i}`
      const table = obj(entry, tableAt)
      const name = str(required(table, 'name', tableAt), `${tableAt}/name`)
      oneOf(required(table, 'status', tableAt), ['new', 'changed', 'existing'], `${tableAt}/status`)
      const columns = arr(required(table, 'columns', tableAt), `${tableAt}/columns`).map((column, j) => {
        const columnAt = `${tableAt}/columns/${j}`
        const record = obj(column, columnAt)
        const columnName = str(required(record, 'name', columnAt), `${columnAt}/name`)
        str(required(record, 'type', columnAt), `${columnAt}/type`)
        if (record.chip !== undefined && record.chip !== null) oneOf(record.chip, ['PK', 'FK', 'UQ'], `${columnAt}/chip`)
        optional(record, 'highlight', bool, columnAt)
        return columnName
      })
      optional(table, 'moreColumns', str, tableAt)
      columnsByTable.set(name, columns)
    })
    const refs = arr(required(record, 'refs', at), `${at}/refs`)
    if (refs.length > 6) fail(at, 'at most 6 refs (fk and json together)')
    refs.forEach((entry, i) => {
      const refAt = `${at}/refs/${i}`
      const ref = obj(entry, refAt)
      for (const end of ['from', 'to']) {
        const pair = arr(required(ref, end, refAt), `${refAt}/${end}`)
        if (pair.length !== 2) fail(`${refAt}/${end}`, 'must be [table, column]')
        const table = str(pair[0], `${refAt}/${end}/0`)
        const column = str(pair[1], `${refAt}/${end}/1`)
        const known = columnsByTable.get(table)
        if (!known) fail(`${refAt}/${end}/0`, `unknown table "${table}"`)
        else if (!known.includes(column)) fail(`${refAt}/${end}/1`, `unknown column "${column}" on table "${table}"`)
      }
      oneOf(required(ref, 'kind', refAt), ['fk', 'json'], `${refAt}/kind`)
    })
  }, pointer)
}

/** True for a YYYY-MM-DD string that names a real calendar date (rejects 2026-02-30). */
function isCalendarDate(text: string): boolean {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(text)
  if (!match) return false
  const [year, month, day] = [Number(match[1]), Number(match[2]), Number(match[3])]
  const parsed = new Date(Date.UTC(year, month - 1, day))
  parsed.setUTCFullYear(year)
  return parsed.getUTCFullYear() === year && parsed.getUTCMonth() === month - 1 && parsed.getUTCDate() === day
}

function checkApproach(value: unknown, pointer: string, flowStages: string[], stageCount: number): string {
  const approach = obj(value, pointer)
  const id = str(required(approach, 'id', pointer), `${pointer}/id`)
  if (!/^[A-Z]$/.test(id)) fail(`${pointer}/id`, 'must be a single capital letter')
  for (const key of ['title', 'overview', 'revision', 'schemaChange']) str(required(approach, key, pointer), `${pointer}/${key}`)
  arr(required(approach, 'anchors', pointer), `${pointer}/anchors`).forEach((entry, i) => {
    const at = `${pointer}/anchors/${i}`
    const anchor = obj(entry, at)
    str(required(anchor, 'repo', at), `${at}/repo`)
    str(required(anchor, 'commit', at), `${at}/commit`)
  })
  const readAt = str(required(approach, 'readAt', pointer), `${pointer}/readAt`)
  if (!isCalendarDate(readAt)) fail(`${pointer}/readAt`, 'must be a real date in YYYY-MM-DD form')
  optional(approach, 'specMarkdown', str, pointer)
  const repoNames = new Set<string>()
  arr(required(approach, 'repos', pointer), `${pointer}/repos`).forEach((entry, i) => {
    const at = `${pointer}/repos/${i}`
    const repo = obj(entry, at)
    const repoName = str(required(repo, 'name', at), `${at}/name`)
    if (repoNames.has(repoName)) fail(`${at}/name`, `duplicate repo name "${repoName}"`)
    repoNames.add(repoName)
    int(required(repo, 'files', at), `${at}/files`)
  })
  strings(required(approach, 'hotPaths', pointer), `${pointer}/hotPaths`)
  const deploy = obj(required(approach, 'deploy', pointer), `${pointer}/deploy`)
  oneOf(required(deploy, 'status', `${pointer}/deploy`), ['stated', 'implied', 'not-stated'], `${pointer}/deploy/status`)
  strings(required(deploy, 'steps', `${pointer}/deploy`), `${pointer}/deploy/steps`)
  if (required(approach, 'criticalPath', pointer) !== null) str(approach.criticalPath, `${pointer}/criticalPath`)
  const slices = arr(required(approach, 'slices', pointer), `${pointer}/slices`)
  const sliceIds = new Set<string>()
  slices.forEach((slice, i) => {
    checkSlice(slice, `${pointer}/slices/${i}`)
    const sliceId = (slice as Record<string, unknown>).id as string
    if (sliceIds.has(sliceId)) fail(`${pointer}/slices/${i}/id`, `duplicate slice id "${sliceId}"`)
    sliceIds.add(sliceId)
  })
  checkFlow(approach, flowStages, pointer)
  checkSequence(approach, pointer)
  checkSchema(approach, pointer)
  optional(approach, 'exampleTrace', (trace, at) => {
    strings(trace, at)
    if ((trace as unknown[]).length !== stageCount) fail(at, `must have ${stageCount} entries, one per example.stages`)
  }, pointer)
  optional(approach, 'restsOn', strings, pointer)
  optional(approach, 'undo', (undo, at) => {
    const record = obj(undo, at)
    for (const key of ['flagOff', 'hardToReverse', 'cheapestNext']) str(required(record, key, at), `${at}/${key}`)
  }, pointer)
  optional(approach, 'rivalClaims', (claims, at) => {
    for (const [key, list] of Object.entries(obj(claims, at))) strings(list, `${at}/${key}`)
  }, pointer)
  optional(approach, 'effortGaps', strings, pointer)
  return id
}

function checkGuidance(value: unknown, approachIds: string[], requirementIds: Set<string>): void {
  const guidance = obj(value, '/guidance')
  str(required(guidance, 'intro', '/guidance'), '/guidance/intro')
  arr(required(guidance, 'steps', '/guidance'), '/guidance/steps').forEach((entry, i) => {
    const at = `/guidance/steps/${i}`
    const step = obj(entry, at)
    str(required(step, 'title', at), `${at}/title`)
    str(required(step, 'body', at), `${at}/body`)
    const tab = required(step, 'tab', at)
    if (typeof tab !== 'string' || !TAB_KEYS.includes(tab)) fail(at, `tab must be one of ${TAB_KEYS.join(', ')}`)
  })
  strings(required(guidance, 'questions', '/guidance'), '/guidance/questions')
  const recommendationAt = '/guidance/recommendation'
  const recommendation = obj(required(guidance, 'recommendation', '/guidance'), recommendationAt)
  const pick = str(required(recommendation, 'approachId', recommendationAt), `${recommendationAt}/approachId`)
  if (!approachIds.includes(pick)) fail(recommendationAt, `approachId "${pick}" is not an approach`)
  for (const key of ['headline', 'confidenceReason']) str(required(recommendation, key, recommendationAt), `${recommendationAt}/${key}`)
  oneOf(required(recommendation, 'confidence', recommendationAt), ['low', 'medium', 'high'], `${recommendationAt}/confidence`)
  for (const key of ['why', 'costs', 'changeMyMind']) strings(required(recommendation, key, recommendationAt), `${recommendationAt}/${key}`)
  arr(required(guidance, 'suggestedChallenges', '/guidance'), '/guidance/suggestedChallenges').forEach((entry, i) => {
    const at = `/guidance/suggestedChallenges/${i}`
    const challenge = obj(entry, at)
    const requirementId = str(required(challenge, 'requirementId', at), `${at}/requirementId`)
    if (!requirementIds.has(requirementId)) fail(at, `unknown requirement "${requirementId}"`)
    const approachId = str(required(challenge, 'approachId', at), `${at}/approachId`)
    if (!approachIds.includes(approachId)) fail(at, `unknown approach "${approachId}"`)
    str(required(challenge, 'note', at), `${at}/note`)
    if (!isScoreStatus(required(challenge, 'want', at))) fail(`${at}/want`, `must be one of ${SCORE_STATUSES.join(', ')}`)
  })
  optional(guidance, 'changeNote', str, '/guidance')
}

/** Fails at the first integer beyond +-(2^53-1); same rule and pointers as the Python validator, so both sides hash the same numbers. */
function checkSafeIntegers(value: unknown, pointer: string): void {
  if (Array.isArray(value)) value.forEach((item, i) => checkSafeIntegers(item, `${pointer}/${i}`))
  else if (isRecord(value)) for (const [key, item] of Object.entries(value)) checkSafeIntegers(item, `${pointer}/${key.replace(/~/g, '~0').replace(/\//g, '~1')}`)
  else if (typeof value === 'number' && Number.isInteger(value) && !Number.isSafeInteger(value)) fail(pointer, 'integer is outside the safe range of +-2^53-1')
}

function validateComparison(value: unknown, spec?: LogicSpec): Comparison {
  const root = obj(value, '')
  checkSafeIntegers(root, '')
  if (root.kind !== COMPARISON_KIND) fail('/kind', `must be "${COMPARISON_KIND}"`)
  if (root.schemaVersion !== 1) fail('/schemaVersion', 'must be 1')
  const builtAgainst = obj(required(root, 'builtAgainst', ''), '/builtAgainst')
  str(required(builtAgainst, 'signoffRenderId', '/builtAgainst'), '/builtAgainst/signoffRenderId')

  const approachList = arr(required(root, 'approaches', ''), '/approaches')
  if (approachList.length < 2 || approachList.length > 5) fail('/approaches', 'must hold 2 to 5 approaches')

  const example = root.example
  if (example !== undefined) {
    const record = obj(example, '/example')
    str(required(record, 'scenario', '/example'), '/example/scenario')
    strings(required(record, 'stages', '/example'), '/example/stages')
  }
  const stageCount = example === undefined ? 0 : (obj(example, '/example').stages as unknown[]).length
  let flowStages: string[] = []
  if (root.flowStages !== undefined) {
    strings(root.flowStages, '/flowStages')
    flowStages = root.flowStages as string[]
    if (flowStages.length < 3 || flowStages.length > 8) fail('/flowStages', 'must hold 3 to 8 stages')
  }

  const approachIds: string[] = []
  approachList.forEach((approach, i) => {
    const id = checkApproach(approach, `/approaches/${i}`, flowStages, stageCount)
    if (approachIds.includes(id)) fail(`/approaches/${i}/id`, `duplicate approach id "${id}"`)
    approachIds.push(id)
  })
  approachList.forEach((approach, i) => {
    const claims = (approach as Record<string, unknown>).rivalClaims
    if (claims === undefined) return
    const at = `/approaches/${i}/rivalClaims`
    const ownId = (approach as Record<string, unknown>).id
    for (const key of Object.keys(claims as Record<string, unknown>)) {
      if (!approachIds.includes(key)) fail(`${at}/${key}`, `unknown approach "${key}"`)
      if (key === ownId) fail(`${at}/${key}`, 'an approach cannot rival itself')
    }
  })

  const scores = obj(required(root, 'scores', ''), '/scores')
  const requirements = spec?.requirements
  const requirementIds = new Set<string>(requirements ? requirements.map((r) => r.id) : Object.keys(scores))
  for (const [requirementId, row] of Object.entries(scores)) {
    const rowAt = `/scores/${requirementId}`
    if (!requirementIds.has(requirementId)) fail(rowAt, `unknown requirement "${requirementId}"`)
    for (const [approachId, score] of Object.entries(obj(row, rowAt))) {
      if (!approachIds.includes(approachId)) fail(`${rowAt}/${approachId}`, `unknown approach "${approachId}"`)
      checkScore(score, `${rowAt}/${approachId}`)
    }
  }
  for (const requirement of requirements ?? []) {
    if (requirement.scope === 'out') continue
    const row = scores[requirement.id]
    if (row === undefined) fail(`/scores/${requirement.id}`, 'in-scope requirement has no scores')
    for (const approachId of approachIds) {
      if ((row as Record<string, unknown>)[approachId] === undefined) fail(`/scores/${requirement.id}/${approachId}`, `missing score for approach "${approachId}"`)
    }
  }

  optional(root, 'findings', (findings, at) => {
    arr(findings, at).forEach((entry, i) => {
      const findingAt = `${at}/${i}`
      const finding = obj(entry, findingAt)
      const requirementId = str(required(finding, 'requirementId', findingAt), `${findingAt}/requirementId`)
      if (!requirementIds.has(requirementId)) fail(findingAt, `unknown requirement "${requirementId}"`)
      const named = required(finding, 'approaches', findingAt)
      if (named !== 'all') {
        arr(named, `${findingAt}/approaches`).forEach((approachId, j) => {
          if (typeof approachId !== 'string' || !approachIds.includes(approachId)) fail(`${findingAt}/approaches/${j}`, 'unknown approach')
        })
      }
      oneOf(required(finding, 'type', findingAt), ['disputes', 'same score, different design'], `${findingAt}/type`)
      str(required(finding, 'text', findingAt), `${findingAt}/text`)
      const citation = str(required(finding, 'citation', findingAt), `${findingAt}/citation`)
      if (citation === '') fail(`${findingAt}/citation`, 'must not be empty')
    })
  }, '')
  optional(root, 'pairings', (pairings, at) => {
    arr(pairings, at).forEach((entry, i) => {
      const pairingAt = `${at}/${i}`
      const pairing = obj(entry, pairingAt)
      str(required(pairing, 'name', pairingAt), `${pairingAt}/name`)
      for (const [key, text] of Object.entries(obj(required(pairing, 'items', pairingAt), `${pairingAt}/items`))) {
        if (!approachIds.includes(key)) fail(`${pairingAt}/items/${key}`, `unknown approach "${key}"`)
        str(text, `${pairingAt}/items/${key}`)
      }
      str(required(pairing, 'text', pairingAt), `${pairingAt}/text`)
    })
  }, '')
  optional(root, 'choices', (choices, at) => {
    arr(choices, at).forEach((entry, i) => {
      const choiceAt = `${at}/${i}`
      const choice = obj(entry, choiceAt)
      str(required(choice, 'question', choiceAt), `${choiceAt}/question`)
      for (const [key, text] of Object.entries(obj(required(choice, 'answers', choiceAt), `${choiceAt}/answers`))) {
        if (!approachIds.includes(key)) fail(`${choiceAt}/answers/${key}`, `unknown approach "${key}"`)
        str(text, `${choiceAt}/answers/${key}`)
      }
    })
  }, '')
  optional(root, 'keyDifferences', strings, '')
  if (root.guidance !== undefined) checkGuidance(root.guidance, approachIds, requirementIds)
  return root as unknown as Comparison
}

/** Accepts a parsed `comparison.json`, returning the first failing JSON pointer otherwise. Without a `spec`, rules that need the signed requirements (unknown requirement, missing score) are checked against the comparison's own score keys. */
export function isComparison(value: unknown, spec?: LogicSpec): ComparisonResult {
  try {
    return { ok: true, value: validateComparison(value, spec) }
  } catch (error) {
    if (error instanceof Invalid) return { ok: false, pointer: error.pointer || '/', message: error.message }
    throw error
  }
}

// ---------------------------------------------------------------------------
// Persistent state

const ISO_DATE_TIME = /^\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(\.\d+)?([Zz]|[+-]\d{2}:\d{2})?$/

const stateKey = (slug: string) => `quirk-compare:${slug}`

const freshState = (comparisonId: string): CompareState => ({
  comparisonId,
  drafts: [],
  needsLook: [],
  stars: [],
  focus: 'all',
  includeConditional: true,
  droppedStars: [],
  lastExport: null,
})

const isStringArray = (value: unknown): value is string[] => Array.isArray(value) && value.every((item) => typeof item === 'string')

function isDraft(value: unknown): value is Draft {
  if (!isRecord(value) || typeof value.id !== 'string' || typeof value.note !== 'string' || typeof value.targetHash !== 'string' || !isRecord(value.target)) return false
  const target = value.target
  if (target.type === 'score') return typeof target.requirementId === 'string' && typeof target.approachId === 'string' && isScoreStatus(value.want)
  if (target.type === 'slice') return typeof target.approachId === 'string' && typeof target.sliceId === 'string' && isSizeLabel(value.want)
  return false
}

function isStoredState(value: unknown): value is CompareState {
  if (!isRecord(value) || typeof value.comparisonId !== 'string') return false
  if (!Array.isArray(value.drafts) || !value.drafts.every(isDraft) || !Array.isArray(value.needsLook) || !value.needsLook.every(isDraft)) return false
  if (!isStringArray(value.stars) || !isStringArray(value.droppedStars) || typeof value.focus !== 'string' || typeof value.includeConditional !== 'boolean') return false
  if (value.lastExport === null) return true
  const last = value.lastExport
  return isRecord(last) && typeof last.at === 'string' && isRecord(last.approachRevisions) && isRecord(last.scoreHashes) && (last.historyCounts === undefined || isRecord(last.historyCounts))
}

function resolveTarget(comparison: Comparison, target: Draft['target']): Score | Slice | undefined {
  if (target.type === 'score') return comparison.scores[target.requirementId]?.[target.approachId]
  return comparison.approaches.find((approach) => approach.id === target.approachId)?.slices.find((slice) => slice.id === target.sliceId)
}

function currentHash(comparison: Comparison, target: Draft['target']): string | null {
  const resolved = resolveTarget(comparison, target)
  return resolved ? targetHash(resolved, target.type) : null
}

/** Splits starred requirement ids into those still scored by the comparison and in scope in the spec, and those to drop. Used for both stored state and imported exports. */
export function partitionStars(stars: readonly string[], comparison: Comparison, spec: LogicSpec): { kept: string[]; dropped: string[] } {
  const inScope = new Set(visibleRequirements(spec, { includeConditional: true }).map((requirement) => requirement.id))
  const kept: string[] = []
  const dropped: string[] = []
  for (const star of stars) (comparison.scores[star] && inScope.has(star) ? kept : dropped).push(star)
  return { kept, dropped }
}

function carryOver(stored: CompareState, comparison: Comparison, comparisonId: string, spec: LogicSpec): CompareState {
  const drafts: Draft[] = []
  const needsLook = [...stored.needsLook]
  for (const draft of stored.drafts) {
    if (currentHash(comparison, draft.target) === draft.targetHash) drafts.push(draft)
    else needsLook.push(draft)
  }
  const { kept: stars, dropped: droppedStars } = partitionStars(stored.stars, comparison, spec)
  const ids = comparison.approaches.map((approach) => approach.id)
  const focusKept = stored.focus === 'all' || (stored.focus.length === 2 && [...stored.focus].every((id) => ids.includes(id)))
  return { ...stored, comparisonId, drafts, needsLook, stars, droppedStars, focus: focusKept ? stored.focus : 'all' }
}

/** Loads the reviewer's stage-3 state. A state saved against a different comparison keeps drafts whose target is unchanged, moves the rest to `needsLook`, and drops stars for requirements the comparison no longer scores or the spec now puts out of scope. `storageOk` is false when browser storage is unreadable. */
export function loadCompareState(slug: string, comparison: Comparison, comparisonId: string, spec: LogicSpec): { state: CompareState; storageOk: boolean } {
  let raw: string | null = null
  try {
    raw = localStorage.getItem(stateKey(slug))
  } catch {
    return { state: freshState(comparisonId), storageOk: false }
  }
  if (raw === null) return { state: freshState(comparisonId), storageOk: true }
  let stored: unknown
  try {
    stored = JSON.parse(raw)
  } catch {
    return { state: freshState(comparisonId), storageOk: true }
  }
  if (!isStoredState(stored)) return { state: freshState(comparisonId), storageOk: true }
  return { state: stored.comparisonId === comparisonId ? stored : carryOver(stored, comparison, comparisonId, spec), storageOk: true }
}

/** Persists the state; returns false when browser storage rejects the write. */
export function saveCompareState(slug: string, state: CompareState): boolean {
  try {
    localStorage.setItem(stateKey(slug), JSON.stringify(state))
    return true
  } catch {
    return false
  }
}

// ---------------------------------------------------------------------------
// Derived views

/** The approaches the reviewer is looking at: all of them, or the focused pair when both ids still exist. */
export function focusApproaches(comparison: Comparison, state: CompareState): string[] {
  const ids = comparison.approaches.map((approach) => approach.id)
  if (state.focus === 'all') return ids
  const pair = [...state.focus]
  return pair.length === 2 && pair.every((id) => ids.includes(id)) ? ids.filter((id) => pair.includes(id)) : ids
}

/** In-scope requirements, leaving out conditional ones when the reviewer excluded them. */
export function visibleRequirements(spec: LogicSpec, state: Pick<CompareState, 'includeConditional'>): Requirement[] {
  return spec.requirements.filter((requirement) => requirement.scope !== 'out' && (state.includeConditional || !requirement.condition))
}

/** Requirement ids shown before "+ N all approaches meet": scores differ across the focus, no focused approach fully meets it, or a finding touches the focus. */
export function defaultRows(comparison: Comparison, spec: LogicSpec, state: CompareState): string[] {
  const focus = focusApproaches(comparison, state)
  const findings = comparison.findings ?? []
  return visibleRequirements(spec, state)
    .filter((requirement) => {
      const statuses = focus.map((id) => comparison.scores[requirement.id]?.[id]?.status)
      const qualifiers = focus.map((id) => comparison.scores[requirement.id]?.[id]?.qualifier ?? null)
      const differs = new Set(statuses).size > 1 || (focus.length === 2 && new Set(qualifiers).size > 1)
      const nobodyMeets = !statuses.includes('met')
      const hasFinding = findings.some((finding) => finding.requirementId === requirement.id && (finding.approaches === 'all' || finding.approaches.some((id) => focus.includes(id))))
      return differs || nobodyMeets || hasFinding
    })
    .map((requirement) => requirement.id)
}

/** True when a focused pair truly agrees on a requirement: same status and qualifier on both scores, and no finding touching either approach. A missing score never counts as agreement. */
export function pairAgrees(comparison: Comparison, requirementId: string, pair: string[]): boolean {
  const [first, second] = pair.map((id) => comparison.scores[requirementId]?.[id])
  if (pair.length !== 2 || !first || !second) return false
  if (first.status !== second.status || (first.qualifier ?? null) !== (second.qualifier ?? null)) return false
  return !(comparison.findings ?? []).some((finding) => finding.requirementId === requirementId && (finding.approaches === 'all' || finding.approaches.some((id) => pair.includes(id))))
}

const emptyCounts = (): Record<ScoreStatus, number> => ({ met: 0, 'met with workaround': 0, 'very hard': 0, 'not met': 0 })

/** Status counts for one approach over the visible requirements: `min` for the must-have group, `increments` for every other group. `notFullyMet` lists requirement ids not scored `met`. */
export function coverageCounts(comparison: Comparison, spec: LogicSpec, state: CompareState, approachId: string): {
  min: Record<ScoreStatus, number>
  increments: Record<ScoreStatus, number>
  notFullyMet: string[]
} {
  const result = { min: emptyCounts(), increments: emptyCounts(), notFullyMet: [] as string[] }
  for (const requirement of visibleRequirements(spec, state)) {
    const score = comparison.scores[requirement.id]?.[approachId]
    if (!score) continue
    result[requirement.group === 'min' ? 'min' : 'increments'][score.status] += 1
    if (score.status !== 'met') result.notFullyMet.push(requirement.id)
  }
  return result
}

/** How many of the scores on the focused approaches' visible requirements carry a `check`, out of all of them. */
export function checkedScoreCounts(comparison: Comparison, spec: LogicSpec, state: CompareState): { checked: number; total: number } {
  const focus = focusApproaches(comparison, state)
  let checked = 0
  let total = 0
  for (const requirement of visibleRequirements(spec, state)) {
    for (const id of focus) {
      const score = comparison.scores[requirement.id]?.[id]
      if (!score) continue
      total += 1
      if (score.check !== undefined) checked += 1
    }
  }
  return { checked, total }
}

/** Summed `[low, high]` points of an approach's slices in one band. */
export function pointsFor(approach: Approach, band: Band): [number, number] {
  let low = 0
  let high = 0
  for (const slice of approach.slices) {
    if (slice.band !== band) continue
    low += POINT_MAP[slice.size][0]
    high += POINT_MAP[slice.size][1]
  }
  return [low, high]
}

/** MRs per repo for one slice, `ceil(lines / 500)` at each end of its line range; slices are never merged. */
export function mrsFor(slice: Slice): Record<string, [number, number]> {
  const result: Record<string, [number, number]> = {}
  for (const [repo, [low, high]] of Object.entries(slice.lines ?? {})) result[repo] = [Math.ceil(low / MR_LINES), Math.ceil(high / MR_LINES)]
  return result
}

/** Whether the requirement's signed text changed after this score was written. Pass `requirementId` to compare against the current hash; without it the score is stale when no current requirement carries its hash. */
export function staleScore(score: Score, spec: LogicSpec, itemHashes: Record<string, string>, requirementId?: string): { stale: boolean; oldText: string; newText: string } {
  const current = requirementId === undefined ? undefined : spec.requirements.find((requirement) => requirement.id === requirementId)
  const currentHashValue = requirementId === undefined ? undefined : itemHashes[requirementId]
  const stale = requirementId === undefined ? !Object.values(itemHashes).includes(score.requirementHash) : currentHashValue !== undefined && currentHashValue !== score.requirementHash
  return { stale, oldText: score.requirementText, newText: current?.text ?? score.requirementText }
}

/** Requirement ids whose score for this approach changed since the last export while gaining no `history` entry (a challenge answer) since then. */
export function revisedRows(comparison: Comparison, state: CompareState, approachId: string): string[] {
  const last = state.lastExport
  if (!last) return []
  const rows: string[] = []
  for (const [requirementId, row] of Object.entries(comparison.scores)) {
    const score = row[approachId]
    const key = `${requirementId}|${approachId}`
    const before = last.scoreHashes[key]
    if (!score || before === undefined || before === targetHash(score, 'score')) continue
    const gained = (score.history?.length ?? 0) > (last.historyCounts?.[key] ?? 0)
    if (!gained) rows.push(requirementId)
  }
  return rows
}

/** Repos anchored at different commits across approaches, keyed by repo name. */
export function anchorMismatch(comparison: Comparison): Record<string, boolean> {
  const commits: Record<string, Set<string>> = {}
  for (const approach of comparison.approaches) {
    for (const anchor of approach.anchors) (commits[anchor.repo] ??= new Set()).add(anchor.commit)
  }
  return Object.fromEntries(Object.entries(commits).map(([repo, set]) => [repo, set.size > 1]))
}

/** Notes shown under the recommendation: starred requirements the pick doesn't fully meet, conditional requirements left out, and a pair focus that excludes the pick. */
export function guidanceNotes(comparison: Comparison, spec: LogicSpec, state: CompareState): string[] {
  const recommendation = comparison.guidance?.recommendation
  if (!recommendation) return []
  const pick = recommendation.approachId
  const notes: string[] = []
  const missed = state.stars.filter((id) => {
    const status = comparison.scores[id]?.[pick]?.status
    return status !== undefined && status !== 'met'
  })
  if (missed.length) notes.push(`Approach ${pick} does not fully meet your must-have${missed.length > 1 ? 's' : ''}: ${missed.join(', ')}.`)
  if (!state.includeConditional) {
    const left = spec.requirements.filter((requirement) => requirement.scope !== 'out' && requirement.condition).map((requirement) => requirement.id)
    if (left.length) notes.push(`Conditional requirements are left out of this view: ${left.join(', ')}.`)
  }
  if (!focusApproaches(comparison, state).includes(pick) && state.focus !== 'all') notes.push(`Your focus on ${[...state.focus].join(' and ')} leaves out the recommended approach ${pick}.`)
  return notes
}

// ---------------------------------------------------------------------------
// Export

/** History length for every score, keyed `"<REQ>|<approach>"`; store as `lastExport.historyCounts` when exporting. */
export function allHistoryCounts(comparison: Comparison): Record<string, number> {
  const counts: Record<string, number> = {}
  for (const [requirementId, row] of Object.entries(comparison.scores)) {
    for (const [approachId, score] of Object.entries(row)) counts[`${requirementId}|${approachId}`] = score.history?.length ?? 0
  }
  return counts
}

/** Targets hash for every score, keyed `"<REQ>|<approach>"`; store as `lastExport.scoreHashes` when exporting. */
export function allScoreHashes(comparison: Comparison): Record<string, string> {
  const hashes: Record<string, string> = {}
  for (const [requirementId, row] of Object.entries(comparison.scores)) {
    for (const [approachId, score] of Object.entries(row)) hashes[`${requirementId}|${approachId}`] = targetHash(score, 'score')
  }
  return hashes
}

/** Builds the stage-3 export from the reviewer's drafts and stars; drafts in `needsLook` stay out until the reviewer re-confirms them. */
export function createCompareExport(slug: string, renderId: string, comparisonId: string, comparison: Comparison, state: CompareState): CompareExport {
  return {
    kind: COMPARE_EXPORT_KIND,
    schemaVersion: 1,
    slug,
    renderId,
    comparisonId,
    exportedAt: new Date().toISOString(),
    challenges: state.drafts.map((draft) => ({ id: draft.id, target: draft.target, note: draft.note, want: draft.want, targetHash: draft.targetHash })),
    stars: [...state.stars],
    approachRevisions: Object.fromEntries(comparison.approaches.map((approach) => [approach.id, approach.revision])),
  }
}

/** Shape check for a stage-3 export; whether its targets still resolve against a comparison is the caller's concern. */
export function isCompareExport(value: unknown): boolean {
  if (!isRecord(value) || value.kind !== COMPARE_EXPORT_KIND || value.schemaVersion !== 1) return false
  for (const key of ['slug', 'renderId', 'comparisonId', 'exportedAt']) if (typeof value[key] !== 'string') return false
  if (!ISO_DATE_TIME.test(value.exportedAt as string) || Number.isNaN(Date.parse(value.exportedAt as string))) return false
  if (!isStringArray(value.stars) || !isRecord(value.approachRevisions)) return false
  if (!Object.values(value.approachRevisions).every((revision) => typeof revision === 'string')) return false
  if (!Array.isArray(value.challenges)) return false
  const ids = new Set<string>()
  for (const challenge of value.challenges) {
    if (!isExportChallenge(challenge) || ids.has(challenge.id)) return false
    ids.add(challenge.id)
  }
  return true
}

const isFilled = (value: unknown): value is string => typeof value === 'string' && value.trim() !== ''

/** A challenge the Python `check-export` accepts: every string it requires is non-blank, on top of the draft shape. */
function isExportChallenge(value: unknown): value is Draft {
  if (!isDraft(value) || !isFilled(value.id) || !isFilled(value.note) || !isFilled(value.targetHash)) return false
  const target = value.target
  return isFilled(target.approachId) && (target.type === 'score' ? isFilled(target.requirementId) : isFilled(target.sliceId))
}
