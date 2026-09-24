export type Markdown = string
export type IsoDateTime = string
export type RequirementId = string
export type BehaviorId = string
export type ScenarioId = string
export type ConstraintId = string
export type AssumptionId = string
export type BlindSpotId = string
export type StateId = string
export type EntryId = string

export type Placement = 'in' | 'conditional' | 'out'
export type ScopeCondition = 'no-code' | 'under-10' | 'under-30'
export type RequirementGroup = 'min' | 'i3' | 'i2' | 'i1'
export type Provenance = 'you-chose' | 'you-recommended' | 'claude'
export type Certainty = 'confirmed' | 'assumed' | 'unverified'
export type AssumptionRuling = 'build-on' | 'verify-first' | 'wrong'
export type ScenarioChoice = 'spec' | 'custom' | `alt-${number}`
export type ConstraintKind = 'placement' | 'verification' | 'naming' | 'non-goal' | 'other'
export type ConstraintRulingVerb = 'approve' | 'rewrite' | 'reject'
export type ConstraintRuling = 'approved' | 'rewritten' | 'rejected'
export type DisputeKind = 'derivation' | 'scenario'

export interface Amendment {
  date: string
  text: string
}

export interface Behavior {
  id: BehaviorId
  rule: string
  detail?: Markdown
}

export interface Scenario {
  id: ScenarioId
  behavior: BehaviorId
  given: string
  when: string
  then: string
  alternatives: string[]
  explanation: Markdown
  provenance: Provenance
  question?: string
  rationale?: Markdown
  extraReason?: string
  requestId?: string
  dropReason?: string
  reopened?: { requirementId: RequirementId; reason: string; raisedAt: IsoDateTime }
  reapprovedHash?: string
}

export interface Constraint {
  id: ConstraintId
  area: string
  kind: ConstraintKind
  text: string
  provenance: Provenance
  question?: string
  rationale?: Markdown
  requestId?: string
  ruling?: ConstraintRuling
  originalText?: string
  rejectReason?: string
}

export interface Assumption {
  id: AssumptionId
  claim: string
  basis: string
  certainty: Certainty
  ifWrong: string
  affects: string[]
  meaning: Markdown
  check: Markdown
  checkCost: string
  ruling?: AssumptionRuling
  rulingNote?: string
}

export interface BlindSpot {
  id: BlindSpotId
  title: string
  detail: Markdown
  sources: string[]
  resolvedBy?: string
  acceptance?: string
}

export interface Requirement {
  id: RequirementId
  area: string
  text: string
  summary: string
  detail: Markdown
  scope: 'in' | 'out'
  condition?: ScopeCondition
  group: RequirementGroup
  certainty: Certainty | null
  dependsOn: RequirementId[]
  derivedFrom: string[]
  reviewReason?: string
}

export interface ResearchFinding {
  requestId: string
  blindSpotId: BlindSpotId
  summary: Markdown
  detail: Markdown
  answeredAt: IsoDateTime
}

export interface StateMachineState {
  id: StateId
  label: string
  detail: Markdown
  focal?: boolean
}

export interface StateMachineEntry {
  id: EntryId
  label: string
}

export interface StateMachineTransition {
  id: string
  from: StateId | EntryId
  to: StateId
  short: string
  event: Markdown
  reqs: RequirementId[]
  blindSpot?: BlindSpotId
}

export interface StateMachine {
  states: StateMachineState[]
  entries?: StateMachineEntry[]
  transitions: StateMachineTransition[]
}

export interface StoryMap {
  journey: { area: string; label: string }[]
  crossCutting: string[]
}

export interface LogicSections {
  purpose: Markdown
  conceptualModel: Markdown
  dataFlow: Markdown
  decisionsLocked: { area: string; decision: string }[]
  industryInsights: { finding: Markdown; sources: string[] }[]
  scopeNonGoals: Markdown[]
  deferredIdeas: { text: string; techSpec: boolean }[]
  glossary: { term: string; definition: string }[]
}

export interface LogicSpec {
  schemaVersion: 2
  stage: 1 | 2
  title: string
  status: string
  amendments: Amendment[]
  sections: LogicSections
  behaviors: Behavior[]
  scenarios: Scenario[]
  constraints: Constraint[]
  assumptions: Assumption[]
  blindSpots: BlindSpot[]
  research: ResearchFinding[]
  requirements: Requirement[]
  conflicts: [RequirementId, RequirementId][]
  views?: {
    stateMachine?: StateMachine
    storyMap?: StoryMap
  }
  stage1Pin?: {
    signedAt: IsoDateTime
    renderId: string
    itemHashes: Record<string, string>
  }
  signoff?: {
    signedAt: IsoDateTime
    renderId: string
  }
}

export interface ScenarioRequest {
  id: string
  behavior: BehaviorId
  text: string
  requestedAt: IsoDateTime
}

export interface ResearchRequest {
  id: string
  blindSpotId: BlindSpotId
  question: string
  requestedAt: IsoDateTime
}

export interface AssumptionDecision {
  ruling?: AssumptionRuling
  note: string
}

export interface BlindSpotDecision {
  accepted: boolean
  note: string
}

export interface ScenarioOutcome {
  choice: ScenarioChoice
  custom: string
}

export interface ConstraintRulingDecision {
  ruling: ConstraintRulingVerb
  text: string
  reason: string
}

export interface Dispute {
  kind: DisputeKind
  target: RequirementId | null
  reason: string
}

export interface ReviewState {
  stage: 1 | 2
  scenarioOutcomes: Record<ScenarioId, ScenarioOutcome>
  scenarioApproved: Record<ScenarioId, boolean>
  scenarioDrops: Record<ScenarioId, string>
  scenarioRequests: ScenarioRequest[]
  constraintRulings: Record<ConstraintId, ConstraintRulingDecision>
  assumptions: Record<AssumptionId, AssumptionDecision>
  blindSpots: Record<BlindSpotId, BlindSpotDecision>
  researchRequests: ResearchRequest[]
  placements: Record<RequirementId, Placement>
  conditions: Record<RequirementId, ScopeCondition>
  moveReasons: Record<RequirementId, string>
  notes: Record<string, string>
  disputes: Record<RequirementId, Dispute>
  verdict?: 'approve' | 'send-back'
  verdictNote: string
  signedAt?: IsoDateTime
  updatedAt: IsoDateTime
}

export interface DecisionRecord {
  stage: 1 | 2
  verdict: 'approve' | 'send-back' | null
  verdictNote: string
  signedAt: IsoDateTime | null
  scenarios: {
    id: ScenarioId
    approved: boolean
    dropped: string | null
    then: string
    changesSpec: boolean
  }[]
  constraints: {
    id: ConstraintId
    ruling: ConstraintRulingVerb | null
    text: string
    reason: string
  }[]
  assumptions: {
    id: AssumptionId
    ruling: AssumptionRuling | null
    note: string
  }[]
  blindSpots: {
    id: BlindSpotId
    accepted: boolean
    note: string
  }[]
  placements: {
    id: RequirementId
    from: Placement
    to: Placement
    condition: ScopeCondition | null
    reason: string
  }[]
  disputes: {
    requirementId: RequirementId
    kind: DisputeKind
    target: RequirementId | null
    reason: string
  }[]
  scenarioRequests: ScenarioRequest[]
  researchRequests: ResearchRequest[]
  openWarnings: string[]
}

export interface Export {
  kind: 'quirk-logic-spec-decisions'
  schemaVersion: 2
  stage: 1 | 2
  slug: string
  renderId: string
  exportedAt: IsoDateTime
  signed: boolean
  seen: Record<string, string>
  state: ReviewState
  record: DecisionRecord
}

export interface LogicSpecPayload {
  spec: LogicSpec
  slug: string
  renderId: string
  itemHashes: Record<string, string>
  logicMarkdown: string
  priorDecisions: Export | null
}
