import type { LogicSpec } from './spec-types'

export type ScoreStatus = 'met' | 'met with workaround' | 'very hard' | 'not met'
export type SizeLabel = 'S' | 'S-M' | 'M' | 'M-L' | 'L' | 'L-XL' | 'XL'
export type TabKey = 'overview' | 'approaches' | 'effort' | 'blast' | 'tradeoffs'
export type Band = 'v1' | 'fast-follow' | 'optional'

export interface Anchor {
  repo: string
  commit: string
}

export interface FlowBox {
  stage: string
  lane: string
  text: string
  kind: 'new' | 'changed' | 'reused'
  focal?: boolean
}

export interface SequenceMessage {
  from: string
  to: string
  label: string
  kind: 'call' | 'return' | 'async' | 'focal'
}

export interface TableColumn {
  name: string
  type: string
  chip?: 'PK' | 'FK' | 'UQ' | null
  highlight?: boolean
}

export interface Table {
  name: string
  status: 'new' | 'changed' | 'existing'
  columns: TableColumn[]
  moreColumns?: string
}

export interface SchemaRef {
  from: [string, string]
  to: [string, string]
  kind: 'fk' | 'json'
}

export interface Slice {
  id: string
  name: string
  size: SizeLabel
  band: Band
  area: string
  risk: string
  riskHeadline?: string
  lines?: Record<string, [number, number]>
}

export interface ScoreHistory {
  previous: { status: ScoreStatus; qualifier?: string }
  challenge: string
  reply: string
  outcome: 'revised' | 'held'
}

export interface Score {
  status: ScoreStatus
  qualifier?: string
  wording: string
  note: string
  citations: string[]
  requirementHash: string
  requirementText: string
  check?: string
  history?: ScoreHistory[]
}

export interface Approach {
  id: string
  title: string
  overview: string
  revision: string
  anchors: Anchor[]
  readAt: string
  specMarkdown?: string
  repos: { name: string; files: number }[]
  schemaChange: string
  hotPaths: string[]
  deploy: { status: 'stated' | 'implied' | 'not-stated'; steps: string[] }
  criticalPath: string | null
  slices: Slice[]
  flow?: FlowBox[]
  sequence?: { participants: string[]; messages: SequenceMessage[] }
  schema?: { tables: Table[]; refs: SchemaRef[] }
  exampleTrace?: string[]
  restsOn?: string[]
  undo?: { flagOff: string; hardToReverse: string; cheapestNext: string }
  rivalClaims?: Record<string, string[]>
  effortGaps?: string[]
}

export interface Finding {
  requirementId: string
  approaches: string[] | 'all'
  type: 'disputes' | 'same score, different design'
  text: string
  citation: string
}

export interface Pairing {
  name: string
  items: Record<string, string>
  text: string
}

export interface Guidance {
  intro: string
  steps: { title: string; body: string; tab: TabKey }[]
  questions: string[]
  recommendation: {
    approachId: string
    headline: string
    confidence: 'low' | 'medium' | 'high'
    confidenceReason: string
    why: string[]
    costs: string[]
    changeMyMind: string[]
  }
  suggestedChallenges: { requirementId: string; approachId: string; note: string; want: ScoreStatus }[]
  changeNote?: string
}

export interface Comparison {
  kind: 'quirk-approach-comparison'
  schemaVersion: 1
  builtAgainst: { signoffRenderId: string }
  approaches: Approach[]
  scores: Record<string, Record<string, Score>>
  findings?: Finding[]
  pairings?: Pairing[]
  choices?: { question: string; answers: Record<string, string> }[]
  keyDifferences?: string[]
  example?: { scenario: string; stages: string[] }
  flowStages?: string[]
  guidance?: Guidance
}

export interface ScoreTarget {
  type: 'score'
  requirementId: string
  approachId: string
}

export interface SliceTarget {
  type: 'slice'
  approachId: string
  sliceId: string
}

/** A reviewer challenge; the shape of one entry in a stage-3 export. */
export interface Draft {
  id: string
  target: ScoreTarget | SliceTarget
  note: string
  want: ScoreStatus | SizeLabel
  targetHash: string
}

export interface CompareState {
  comparisonId: string
  drafts: Draft[]
  /** Drafts whose target changed in a newer comparison; never re-aimed without the reviewer. */
  needsLook: Draft[]
  stars: string[]
  /** `'all'`, or two approach ids joined, such as `'AB'`. */
  focus: 'all' | string
  includeConditional: boolean
  droppedStars: string[]
  lastExport: {
    at: string
    approachRevisions: Record<string, string>
    /** `"<REQ>|<approach>"` to that score's targetHash at export time. */
    scoreHashes: Record<string, string>
    /** `"<REQ>|<approach>"` to that score's history length at export time; absent in state saved before it existed, read as 0. */
    historyCounts?: Record<string, number>
  } | null
}

export interface CompareExport {
  kind: 'quirk-approach-comparison-challenges'
  schemaVersion: 1
  slug: string
  renderId: string
  comparisonId: string
  exportedAt: string
  challenges: Draft[]
  stars: string[]
  approachRevisions: Record<string, string>
}

export interface CompareViewProps {
  comparison: Comparison
  comparisonId: string
  spec: LogicSpec
  itemHashes: Record<string, string>
  state: CompareState
  update: (recipe: (draft: CompareState) => void) => void
  approaches: string[]
  openRequirement: (id: string) => void
  goToTab: (tab: TabKey) => void
}
