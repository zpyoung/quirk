export type Markdown = string
export type IsoDateTime = string
export type RequirementId = string
export type AssumptionId = string
export type BlindSpotId = string
export type ScenarioId = string
export type StateId = string
export type EntryId = string

export type RequirementScope = 'in' | 'out'
export type Placement = 'in' | 'conditional' | 'out'
export type ScopeCondition = 'no-code' | 'under-10' | 'under-30'
export type RequirementGroup = 'min' | 'i3' | 'i2' | 'i1'
export type Provenance = 'you-chose' | 'you-recommended' | 'claude'
export type Certainty = 'confirmed' | 'assumed' | 'unverified'
export type AssumptionRuling = 'build-on' | 'verify-first' | 'wrong'
export type ScenarioChoice = 'spec' | 'custom' | `alt-${number}`

export interface Amendment {
  date: string
  text: string
}

export interface Requirement {
  id: RequirementId
  area: string
  text: string
  summary: string
  detail: Markdown
  scope: RequirementScope
  condition?: ScopeCondition
  group: RequirementGroup
  provenance: Provenance
  question?: string
  rationale?: Markdown
  certainty: Certainty | null
  dependsOn: RequirementId[]
  reviewReason?: string
}

export interface Assumption {
  id: AssumptionId
  claim: string
  basis: string
  certainty: Certainty
  ifWrong: string
  affects: RequirementId[]
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
  sources: RequirementId[]
  resolvedBy?: RequirementId
  acceptance?: string
}

export interface Scenario {
  id: ScenarioId
  given: string
  when: string
  then: string
  alternatives: string[]
  explanation: Markdown
  refs: RequirementId[]
  requestId?: string
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
  schemaVersion: 1
  title: string
  status: string
  amendments: Amendment[]
  sections: LogicSections
  requirements: Requirement[]
  conflicts: [RequirementId, RequirementId][]
  assumptions: Assumption[]
  blindSpots: BlindSpot[]
  scenarios: Scenario[]
  research: ResearchFinding[]
  views?: {
    stateMachine?: StateMachine
    storyMap?: StoryMap
  }
  signoff?: {
    signedAt: IsoDateTime
    renderId: string
  }
}

export interface ScenarioRequest {
  id: string
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

export interface ReviewState {
  placements: Record<RequirementId, Placement>
  conditions: Record<RequirementId, ScopeCondition>
  moveReasons: Record<RequirementId, string>
  notes: Record<string, string>
  assumptions: Record<AssumptionId, AssumptionDecision>
  blindSpots: Record<BlindSpotId, BlindSpotDecision>
  scenarioOutcomes: Record<ScenarioId, ScenarioOutcome>
  scenarioApproved: Record<ScenarioId, boolean>
  scenarioRequests: ScenarioRequest[]
  researchRequests: ResearchRequest[]
  verdict?: 'approve' | 'send-back'
  verdictNote: string
  signedAt?: IsoDateTime
  updatedAt: IsoDateTime
}

export interface DecisionRecord {
  verdict: 'approve' | 'send-back' | null
  verdictNote: string
  signedAt: IsoDateTime | null
  placements: {
    id: RequirementId
    from: Placement
    to: Placement
    condition: ScopeCondition | null
    reason: string
  }[]
  assumptions: {
    id: AssumptionId
    ruling?: AssumptionRuling
    note: string
  }[]
  blindSpots: {
    id: BlindSpotId
    accepted: boolean
    note: string
  }[]
  scenarios: {
    id: ScenarioId
    approved: boolean
    then: string
    changesSpec: boolean
  }[]
  scenarioRequests: ScenarioRequest[]
  researchRequests: ResearchRequest[]
  openWarnings: string[]
}

export interface Export {
  kind: 'quirk-logic-spec-decisions'
  schemaVersion: 1
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
