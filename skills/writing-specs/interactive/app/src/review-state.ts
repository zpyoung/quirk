import { useEffect, useState } from 'react'
import type {
  Assumption,
  AssumptionRuling,
  BlindSpot,
  ConstraintKind,
  ConstraintRulingDecision,
  ConstraintRulingVerb,
  DecisionRecord,
  Export,
  LogicSpec,
  LogicSpecPayload,
  Placement,
  Requirement,
  ReviewState,
  Scenario,
  ScopeCondition,
} from './spec-types'

export type ViewId = 'board' | 'risks' | 'scenarios' | 'constraints' | 'coverage' | 'heatmap' | 'story-map' | 'states' | 'spec' | 'sign-off'
export type TabSpec = { id: ViewId; label: string }
export type Snapshot = { state: ReviewState; seen: Record<string, string>; lastExportUpdatedAt: string | null; renderId: string | null; storageOk: boolean }
export type PayloadResult = { payload: LogicSpecPayload | null; error: string | null }
export type ReviewGate = { id: string; label: string; done: number; total: number }
export type Update = (recipe: (state: ReviewState) => ReviewState, reviewedItemId?: string) => void
export type RequirementStatus = 'active' | 'withdrawn' | 'flagged'

export const PAYLOAD_ID = 'quirk-logic-spec-payload'
export const EXPORT_KIND = 'quirk-logic-spec-decisions'
export const CHOICE_LABEL: Record<Placement, string> = { in: 'In scope', conditional: 'Conditionally in scope', out: 'Out of scope' }
export const CONDITION_LABEL: Record<ScopeCondition, string> = {
  'no-code': 'No extra code required',
  'under-10': 'Under 10 lines of code',
  'under-30': 'Under 30 lines of code',
}
export const RULINGS: { value: AssumptionRuling; label: string }[] = [
  { value: 'build-on', label: 'Build on it' },
  { value: 'verify-first', label: 'Verify first' },
  { value: 'wrong', label: 'Treat it as wrong' },
]
export const CERTAINTIES = ['confirmed', 'assumed', 'unverified'] as const
export const GROUPS = ['min', 'i3', 'i2', 'i1'] as const
export const GROUP_LABEL: Record<(typeof GROUPS)[number], string> = {
  min: 'Minimum',
  i3: 'Impact 3',
  i2: 'Impact 2',
  i1: 'Impact 1',
}
export const CONSTRAINT_KIND_LABEL: Record<ConstraintKind, string> = {
  placement: 'Placement',
  verification: 'Verification',
  naming: 'Naming',
  'non-goal': 'Non-goal',
  other: 'Other',
}
export const CONSTRAINT_RULING_LABEL: Record<'approve' | 'rewrite' | 'reject', string> = {
  approve: 'Approved',
  rewrite: 'Rewritten',
  reject: 'Rejected',
}

export function emptyState(stage: 1 | 2 = 1): ReviewState {
  return {
    stage,
    scenarioOutcomes: {},
    scenarioApproved: {},
    scenarioDrops: {},
    scenarioRequests: [],
    constraintRulings: {},
    assumptions: {},
    blindSpots: {},
    researchRequests: [],
    placements: {},
    conditions: {},
    moveReasons: {},
    notes: {},
    disputes: {},
    verdictNote: '',
    updatedAt: new Date().toISOString(),
  }
}

export function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

export function isStringMap(value: unknown): value is Record<string, string> {
  return isObject(value) && Object.values(value).every((item) => typeof item === 'string')
}

export function isReviewState(value: unknown): value is ReviewState {
  if (!isObject(value)) return false
  const isPlacement = (item: unknown) => item === 'in' || item === 'conditional' || item === 'out'
  const isCondition = (item: unknown) => item === 'no-code' || item === 'under-10' || item === 'under-30'
  const isRuling = (item: unknown) => item === 'build-on' || item === 'verify-first' || item === 'wrong'
  const isConstraintVerb = (item: unknown) => item === 'approve' || item === 'rewrite' || item === 'reject'
  const isDisputeKind = (item: unknown) => item === 'derivation' || item === 'scenario'
  return (
    (value.stage === 1 || value.stage === 2) &&
    isObject(value.scenarioOutcomes) && Object.values(value.scenarioOutcomes).every((outcome) =>
      isObject(outcome) && typeof outcome.choice === 'string' &&
      (outcome.choice === 'spec' || outcome.choice === 'custom' || /^alt-\d+$/.test(outcome.choice)) &&
      typeof outcome.custom === 'string') &&
    isObject(value.scenarioApproved) && Object.values(value.scenarioApproved).every((approved) => typeof approved === 'boolean') &&
    isStringMap(value.scenarioDrops) &&
    Array.isArray(value.scenarioRequests) && value.scenarioRequests.every((request) =>
      isObject(request) && typeof request.id === 'string' && typeof request.behavior === 'string' &&
      typeof request.text === 'string' && typeof request.requestedAt === 'string') &&
    isObject(value.constraintRulings) && Object.values(value.constraintRulings).every((ruling) =>
      isObject(ruling) && isConstraintVerb(ruling.ruling) && typeof ruling.text === 'string' && typeof ruling.reason === 'string') &&
    isObject(value.assumptions) && Object.values(value.assumptions).every((decision) =>
      isObject(decision) && typeof decision.note === 'string' && (decision.ruling === undefined || isRuling(decision.ruling))) &&
    isObject(value.blindSpots) && Object.values(value.blindSpots).every((decision) =>
      isObject(decision) && typeof decision.accepted === 'boolean' && typeof decision.note === 'string') &&
    Array.isArray(value.researchRequests) && value.researchRequests.every((request) =>
      isObject(request) && typeof request.id === 'string' && typeof request.blindSpotId === 'string' &&
      typeof request.question === 'string' && typeof request.requestedAt === 'string') &&
    isObject(value.placements) && Object.values(value.placements).every(isPlacement) &&
    isObject(value.conditions) && Object.values(value.conditions).every(isCondition) &&
    isStringMap(value.moveReasons) &&
    isStringMap(value.notes) &&
    isObject(value.disputes) && Object.values(value.disputes).every((dispute) =>
      isObject(dispute) && isDisputeKind(dispute.kind) && (dispute.target === null || typeof dispute.target === 'string') && typeof dispute.reason === 'string') &&
    typeof value.verdictNote === 'string' &&
    typeof value.updatedAt === 'string' &&
    (value.verdict === undefined || value.verdict === 'approve' || value.verdict === 'send-back') &&
    (value.signedAt === undefined || typeof value.signedAt === 'string')
  )
}

export function isDecisionExport(value: unknown, slug?: string): value is Export {
  return (
    isObject(value) &&
    value.kind === EXPORT_KIND &&
    value.schemaVersion === 2 &&
    (value.stage === 1 || value.stage === 2) &&
    typeof value.slug === 'string' &&
    (slug === undefined || value.slug === slug) &&
    typeof value.renderId === 'string' &&
    typeof value.exportedAt === 'string' &&
    typeof value.signed === 'boolean' &&
    isStringMap(value.seen) &&
    isReviewState(value.state) &&
    value.stage === value.state.stage &&
    // a signature only means something once its state actually records a signed approval
    (!value.signed || (Boolean(value.state.signedAt) && value.state.verdict === 'approve')) &&
    isObject(value.record)
  )
}

export function isLogicSpec(value: unknown): value is LogicSpec {
  if (!isObject(value) || value.schemaVersion !== 2 || (value.stage !== 1 && value.stage !== 2) ||
      typeof value.title !== 'string' || typeof value.status !== 'string') return false
  if (!Array.isArray(value.behaviors) || !Array.isArray(value.scenarios) || !Array.isArray(value.constraints) ||
      !Array.isArray(value.assumptions) || !Array.isArray(value.blindSpots) || !Array.isArray(value.research) ||
      !Array.isArray(value.requirements) || !Array.isArray(value.conflicts) ||
      !Array.isArray(value.amendments) || !isObject(value.sections)) return false
  const isProvenance = (item: unknown) => ['you-chose', 'you-recommended', 'claude'].includes(String(item))
  if (value.behaviors.some((item) => !isObject(item) || typeof item.id !== 'string' || typeof item.rule !== 'string')) return false
  if (value.scenarios.some((item) => !isObject(item) || typeof item.id !== 'string' || typeof item.behavior !== 'string' ||
      typeof item.given !== 'string' || typeof item.when !== 'string' || typeof item.then !== 'string' ||
      !Array.isArray(item.alternatives) || typeof item.explanation !== 'string' || !isProvenance(item.provenance))) return false
  if (value.constraints.some((item) => !isObject(item) || typeof item.id !== 'string' || typeof item.area !== 'string' ||
      !['placement', 'verification', 'naming', 'non-goal', 'other'].includes(String(item.kind)) ||
      typeof item.text !== 'string' || !isProvenance(item.provenance))) return false
  if (value.assumptions.some((item) => !isObject(item) || typeof item.id !== 'string' || typeof item.claim !== 'string' ||
      typeof item.basis !== 'string' || typeof item.ifWrong !== 'string' || !Array.isArray(item.affects) ||
      typeof item.meaning !== 'string' || typeof item.check !== 'string' || typeof item.checkCost !== 'string')) return false
  if (value.blindSpots.some((item) => !isObject(item) || typeof item.id !== 'string' || typeof item.title !== 'string' ||
      typeof item.detail !== 'string' || !Array.isArray(item.sources))) return false
  if (value.requirements.some((item) => !isObject(item) || typeof item.id !== 'string' || typeof item.area !== 'string' ||
      typeof item.text !== 'string' || typeof item.summary !== 'string' || typeof item.detail !== 'string' ||
      (item.scope !== 'in' && item.scope !== 'out') || !Array.isArray(item.dependsOn) ||
      !item.dependsOn.every((id) => typeof id === 'string') || !Array.isArray(item.derivedFrom) ||
      !item.derivedFrom.every((id) => typeof id === 'string') ||
      !['min', 'i3', 'i2', 'i1'].includes(String(item.group)) ||
      (item.certainty !== null && !['confirmed', 'assumed', 'unverified'].includes(String(item.certainty))))) return false
  if (!isObject(value.sections) || typeof value.sections.purpose !== 'string' ||
      typeof value.sections.conceptualModel !== 'string' || typeof value.sections.dataFlow !== 'string') return false
  if (value.views !== undefined && !isObject(value.views)) return false
  return true
}

export function isPayload(value: unknown): value is LogicSpecPayload {
  return (
    isObject(value) &&
    isLogicSpec(value.spec) &&
    typeof value.slug === 'string' &&
    typeof value.renderId === 'string' &&
    isStringMap(value.itemHashes) &&
    typeof value.logicMarkdown === 'string' &&
    (value.priorDecisions === null || isDecisionExport(value.priorDecisions, value.slug))
  )
}

export function readPayload(): PayloadResult {
  const element = document.getElementById(PAYLOAD_ID)
  if (!element) return { payload: null, error: null }
  try {
    const parsed: unknown = JSON.parse(element.textContent ?? 'null')
    if (parsed === null) return { payload: null, error: null }
    if (!isPayload(parsed)) return { payload: null, error: 'The embedded review data does not match the expected schema.' }
    return { payload: parsed, error: null }
  } catch {
    return { payload: null, error: 'The embedded review data is not valid JSON.' }
  }
}

export function laterThan(a: string, b: string): boolean {
  return (Date.parse(a) || 0) > (Date.parse(b) || 0)
}

export function nextTimestamp(previous?: string): string {
  const now = Date.now()
  const previousTime = previous ? Date.parse(previous) || 0 : 0
  return new Date(Math.max(now, previousTime + 1)).toISOString()
}

export function cloneState(state: ReviewState): ReviewState {
  return {
    ...state,
    scenarioOutcomes: Object.fromEntries(Object.entries(state.scenarioOutcomes).map(([id, outcome]) => [id, { ...outcome }])),
    scenarioApproved: { ...state.scenarioApproved },
    scenarioDrops: { ...state.scenarioDrops },
    scenarioRequests: state.scenarioRequests.map((request) => ({ ...request })),
    constraintRulings: Object.fromEntries(Object.entries(state.constraintRulings).map(([id, ruling]) => [id, { ...ruling }])),
    assumptions: Object.fromEntries(Object.entries(state.assumptions).map(([id, decision]) => [id, { ...decision }])),
    blindSpots: Object.fromEntries(Object.entries(state.blindSpots).map(([id, decision]) => [id, { ...decision }])),
    researchRequests: state.researchRequests.map((request) => ({ ...request })),
    placements: { ...state.placements },
    conditions: { ...state.conditions },
    moveReasons: { ...state.moveReasons },
    notes: { ...state.notes },
    disputes: Object.fromEntries(Object.entries(state.disputes).map(([id, dispute]) => [id, { ...dispute }])),
  }
}

/** Every reviewable item id in the logic, mirroring the Python `item_hashes` key set. */
export function itemIds(spec: LogicSpec): string[] {
  return [...spec.behaviors, ...spec.scenarios, ...spec.constraints, ...spec.assumptions, ...spec.blindSpots, ...spec.requirements].map((item) => item.id)
}

/**
 * `CONTRACT:` computed, never stored; Python implements this identically (see Derived-requirement status).
 * withdrawn: every derivedFrom id is a reopened scenario. flagged: some but not all are. active: none are.
 */
export function requirementStatus(requirement: Requirement, spec: LogicSpec): RequirementStatus {
  const reopenedScenarioIds = new Set(spec.scenarios.filter((scenario) => scenario.reopened).map((scenario) => scenario.id))
  const reopenedCount = requirement.derivedFrom.filter((id) => reopenedScenarioIds.has(id)).length
  if (reopenedCount === 0) return 'active'
  return reopenedCount === requirement.derivedFrom.length ? 'withdrawn' : 'flagged'
}

export function changedItemIds(spec: LogicSpec, hashes: Record<string, string>, seen: Record<string, string>): string[] {
  const hashChanged = itemIds(spec).filter((id) => seen[id] !== hashes[id])
  const derivationChanged = spec.requirements
    .filter((requirement) => requirementStatus(requirement, spec) !== 'active')
    .map((requirement) => requirement.id)
  return [...new Set([...hashChanged, ...derivationChanged])]
}

export function retainItemIds<T>(values: Record<string, T>, allowed: Set<string>): Record<string, T> {
  const retained: Record<string, T> = {}
  for (const [id, value] of Object.entries(values)) {
    if (allowed.has(id)) retained[id] = value
  }
  return retained
}

export function carryOver(
  state: ReviewState,
  seen: Record<string, string>,
  spec: LogicSpec,
  hashes: Record<string, string>,
  priorRenderId: string | null,
  renderId: string,
): { state: ReviewState; changedIds: string[]; seen: Record<string, string> } {
  const scenarioIds = new Set(spec.scenarios.map((item) => item.id))
  const constraintIds = new Set(spec.constraints.map((item) => item.id))
  const assumptionIds = new Set(spec.assumptions.map((item) => item.id))
  const blindSpotIds = new Set(spec.blindSpots.map((item) => item.id))
  const requirementIds = new Set(spec.requirements.map((item) => item.id))
  const allItemIds = new Set([...scenarioIds, ...constraintIds, ...assumptionIds, ...blindSpotIds, ...requirementIds])

  const changedIds = changedItemIds(spec, hashes, seen)
  const currentSeen = retainItemIds(seen, new Set(itemIds(spec)))
  const next = cloneState(state)
  let stateChanged = false
  for (const id of changedIds) {
    stateChanged ||= Object.hasOwn(next.placements, id) || Object.hasOwn(next.conditions, id) ||
      Object.hasOwn(next.moveReasons, id) || Object.hasOwn(next.notes, id) ||
      Object.hasOwn(next.assumptions, id) || Object.hasOwn(next.blindSpots, id) ||
      Object.hasOwn(next.scenarioOutcomes, id) || Object.hasOwn(next.scenarioApproved, id) ||
      Object.hasOwn(next.scenarioDrops, id) || Object.hasOwn(next.constraintRulings, id) ||
      Object.hasOwn(next.disputes, id)
    delete next.placements[id]
    delete next.conditions[id]
    delete next.moveReasons[id]
    delete next.notes[id]
    delete next.assumptions[id]
    delete next.blindSpots[id]
    delete next.scenarioOutcomes[id]
    delete next.scenarioApproved[id]
    delete next.scenarioDrops[id]
    delete next.constraintRulings[id]
    delete next.disputes[id]
  }
  const countsOf = (s: ReviewState) => [
    Object.keys(s.placements).length,
    Object.keys(s.conditions).length,
    Object.keys(s.moveReasons).length,
    Object.keys(s.notes).length,
    Object.keys(s.assumptions).length,
    Object.keys(s.blindSpots).length,
    Object.keys(s.scenarioOutcomes).length,
    Object.keys(s.scenarioApproved).length,
    Object.keys(s.scenarioDrops).length,
    Object.keys(s.constraintRulings).length,
    Object.keys(s.disputes).length,
    s.researchRequests.length,
  ]
  const originalCounts = countsOf(next)
  next.placements = retainItemIds(next.placements, requirementIds)
  next.conditions = retainItemIds(next.conditions, requirementIds)
  next.moveReasons = retainItemIds(next.moveReasons, requirementIds)
  next.notes = retainItemIds(next.notes, allItemIds)
  next.assumptions = retainItemIds(next.assumptions, assumptionIds)
  next.blindSpots = retainItemIds(next.blindSpots, blindSpotIds)
  next.scenarioOutcomes = retainItemIds(next.scenarioOutcomes, scenarioIds)
  next.scenarioApproved = retainItemIds(next.scenarioApproved, scenarioIds)
  next.scenarioDrops = retainItemIds(next.scenarioDrops, scenarioIds)
  next.constraintRulings = retainItemIds(next.constraintRulings, constraintIds)
  next.disputes = retainItemIds(next.disputes, requirementIds)
  next.researchRequests = next.researchRequests.filter((request) => blindSpotIds.has(request.blindSpotId))
  const retainedCounts = countsOf(next)
  stateChanged ||= originalCounts.some((count, index) => count !== retainedCounts[index])
  // unseen items share the signed render's hashes, so only a new render or dropped state voids a signature
  if (priorRenderId !== renderId || stateChanged) {
    if (next.signedAt) {
      next.signedAt = undefined
      stateChanged = true
    }
  }
  if (stateChanged) next.updatedAt = nextTimestamp(next.updatedAt)
  return { state: next, changedIds, seen: currentSeen }
}

export function readLocalSnapshot(key: string): Omit<Snapshot, 'storageOk'> | null {
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return null
    const parsed: unknown = JSON.parse(raw)
    if (!isObject(parsed) || !isReviewState(parsed.state)) return null
    return {
      state: parsed.state,
      seen: isStringMap(parsed.seen) ? parsed.seen : {},
      lastExportUpdatedAt: typeof parsed.lastExportUpdatedAt === 'string' ? parsed.lastExportUpdatedAt : null,
      renderId: typeof parsed.renderId === 'string' ? parsed.renderId : null,
    }
  } catch {
    throw new Error('Browser storage is unavailable.')
  }
}

export function bootstrap(payload: LogicSpecPayload): Snapshot {
  const storageKey = `quirk-logic-spec:${payload.slug}`
  let local: Omit<Snapshot, 'storageOk'> | null = null
  let storageOk = true
  try {
    local = readLocalSnapshot(storageKey)
  } catch {
    storageOk = false
  }
  // a snapshot from the other stage reflects decisions already folded into (or not yet relevant to) this spec
  if (local && local.state.stage !== payload.spec.stage) local = null
  const priorExport = payload.priorDecisions && isDecisionExport(payload.priorDecisions, payload.slug) ? payload.priorDecisions : null
  const prior = priorExport && priorExport.state.stage === payload.spec.stage
    ? {
        state: priorExport.state,
        seen: priorExport.seen,
        lastExportUpdatedAt: priorExport.state.updatedAt,
        renderId: priorExport.renderId,
      }
    : null
  let selected = local ?? prior
  if (local && prior && laterThan(prior.state.updatedAt, local.state.updatedAt)) selected = prior
  if (!selected) selected = { state: emptyState(payload.spec.stage), seen: {}, lastExportUpdatedAt: null, renderId: null }
  const carried = carryOver(selected.state, selected.seen, payload.spec, payload.itemHashes, selected.renderId, payload.renderId)
  return { ...carried, lastExportUpdatedAt: selected.lastExportUpdatedAt, renderId: payload.renderId, storageOk }
}

export function placementInSpec(requirement: Requirement): Placement {
  if (requirement.scope === 'out') return 'out'
  return requirement.condition ? 'conditional' : 'in'
}

/** A requirement's placement always has a value: derived requirements arrive with Claude's placement pre-filled. */
export function effectivePlacement(state: ReviewState, requirement: Requirement): Placement {
  return state.placements[requirement.id] ?? placementInSpec(requirement)
}

export function effectiveCondition(state: ReviewState, requirement: Requirement): ScopeCondition {
  return state.conditions[requirement.id] ?? requirement.condition ?? 'under-10'
}

export function requirementMoved(state: ReviewState, requirement: Requirement): boolean {
  const current = effectivePlacement(state, requirement)
  const original = placementInSpec(requirement)
  return current !== original || (current === 'conditional' && effectiveCondition(state, requirement) !== requirement.condition)
}

export function scopeWarnings(state: ReviewState, spec: LogicSpec): string[] {
  // withdrawn requirements are excluded from the gates entirely, so their dependency and conflict edges are ignored here too
  const requirements = new Map(
    spec.requirements.filter((requirement) => requirementStatus(requirement, spec) !== 'withdrawn').map((requirement) => [requirement.id, requirement]),
  )
  const warnings: string[] = []
  for (const requirement of requirements.values()) {
    const placement = effectivePlacement(state, requirement)
    if (placement === 'out') continue
    const pending = [...requirement.dependsOn]
    const visited = new Set<string>()
    while (pending.length) {
      const dependencyId = pending.pop()
      if (!dependencyId || visited.has(dependencyId)) continue
      visited.add(dependencyId)
      const dependency = requirements.get(dependencyId)
      if (!dependency) continue
      const dependencyPlacement = effectivePlacement(state, dependency)
      if (dependencyPlacement === 'out') {
        warnings.push(`${requirement.id} depends on ${dependencyId} through its dependency chain, which is out of scope.`)
      } else {
        pending.push(...dependency.dependsOn)
      }
    }
  }
  for (const [firstId, secondId] of spec.conflicts) {
    const first = requirements.get(firstId)
    const second = requirements.get(secondId)
    if (!first || !second) continue
    const firstPlacement = effectivePlacement(state, first)
    const secondPlacement = effectivePlacement(state, second)
    if (firstPlacement !== 'out' && secondPlacement !== 'out') {
      warnings.push(`${firstId} and ${secondId} conflict while both are in scope.`)
    }
  }
  return warnings
}

/** `CONTRACT:` a blind spot is active unless its resolvedBy is an approved-and-not-dropped scenario, or a constraint ruled approve/rewrite. Stage 2 reads that ruling from the folded spec fields (reopened scenarios excepted); stage 1 reads it from review state. */
export function activeBlindSpots(state: ReviewState, spec: LogicSpec): BlindSpot[] {
  const scenarios = new Map(spec.scenarios.map((scenario) => [scenario.id, scenario]))
  const constraints = new Map(spec.constraints.map((constraint) => [constraint.id, constraint]))
  const isResolved = (resolvedBy: string): boolean => {
    const scenario = scenarios.get(resolvedBy)
    if (scenario) {
      if (spec.stage === 2 && !scenario.reopened) return !scenario.dropReason
      return Boolean(state.scenarioApproved[resolvedBy]) && !state.scenarioDrops[resolvedBy]
    }
    const constraint = constraints.get(resolvedBy)
    if (constraint) {
      if (spec.stage === 2) return constraint.ruling === 'approved' || constraint.ruling === 'rewritten'
      const ruling = state.constraintRulings[resolvedBy]?.ruling
      return ruling === 'approve' || ruling === 'rewrite'
    }
    return false
  }
  return spec.blindSpots.filter((spot) => !spot.resolvedBy || !isResolved(spot.resolvedBy))
}

export function pendingScenarioRequests(state: ReviewState, spec: LogicSpec) {
  const converted = new Set(spec.scenarios.flatMap((scenario) => scenario.requestId ? [scenario.requestId] : []))
  return state.scenarioRequests.filter((request) => !converted.has(request.id))
}
export function pendingResearchRequests(state: ReviewState, spec: LogicSpec) {
  const answered = new Set(spec.research.map((finding) => finding.requestId))
  return state.researchRequests.filter((request) => !answered.has(request.id))
}

export function scenarioThen(state: ReviewState, scenario: Scenario): string {
  const outcome = state.scenarioOutcomes[scenario.id]
  if (!outcome || outcome.choice === 'spec') return scenario.then
  if (outcome.choice === 'custom') return outcome.custom.trim() || scenario.then
  const index = Number(outcome.choice.slice(4))
  return scenario.alternatives[index] ?? scenario.then
}

/** The next stored ruling for a constraint given a UI patch; switching into `rewrite` starts from blank so the gate can't be satisfied with the original constraint text. */
export function nextConstraintRuling(
  entry: ConstraintRulingDecision | undefined,
  constraintText: string,
  isClaude: boolean,
  patch: { ruling?: ConstraintRulingVerb; text?: string; reason?: string },
): ConstraintRulingDecision {
  const ruling = entry?.ruling ?? (isClaude ? 'approve' : undefined)
  const text = entry?.text ?? constraintText
  const reason = entry?.reason ?? ''
  const switchingToRewrite = patch.ruling === 'rewrite' && ruling !== 'rewrite'
  return {
    ruling: patch.ruling ?? ruling ?? 'approve',
    text: patch.text ?? (switchingToRewrite ? '' : text),
    reason: patch.reason ?? reason,
  }
}

function constraintDecided(state: ReviewState, constraint: { id: string }): boolean {
  const ruling = state.constraintRulings[constraint.id]
  if (!ruling) return false
  if (ruling.ruling === 'rewrite') return Boolean(ruling.text.trim())
  if (ruling.ruling === 'reject') return Boolean(ruling.reason.trim())
  return ruling.ruling === 'approve'
}

/** `CONTRACT:` the TS gate ids and meanings mirror the Python gates exactly (see Gates); the duplication is deliberate. */
export function gateList(state: ReviewState, spec: LogicSpec): ReviewGate[] {
  if (spec.stage === 1) {
    const pending = pendingScenarioRequests(state, spec)
    const scenarioDecided = (scenario: Scenario) => Boolean(state.scenarioApproved[scenario.id] || state.scenarioDrops[scenario.id]?.trim())
    const activeSpots = activeBlindSpots(state, spec)
    const ruled = (assumption: Assumption) => {
      const decision = state.assumptions[assumption.id]
      return Boolean(decision?.ruling && (decision.ruling === 'build-on' || decision.note.trim()))
    }
    return [
      {
        id: 'scenarios',
        label: 'Approve or drop every scenario; resolve pending requests',
        done: spec.scenarios.filter(scenarioDecided).length,
        total: spec.scenarios.length + pending.length,
      },
      { id: 'constraints', label: 'Rule on every constraint', done: spec.constraints.filter((c) => constraintDecided(state, c)).length, total: spec.constraints.length },
      { id: 'assumptions', label: 'Rule on every assumption; explain rulings other than build on', done: spec.assumptions.filter(ruled).length, total: spec.assumptions.length },
      {
        id: 'blind-spots',
        label: 'Accept every active blind spot in your own words',
        done: activeSpots.filter((spot) => state.blindSpots[spot.id]?.accepted && state.blindSpots[spot.id]?.note.trim()).length,
        total: activeSpots.length,
      },
    ]
  }
  const nonWithdrawn = spec.requirements.filter((requirement) => requirementStatus(requirement, spec) !== 'withdrawn')
  const derivedIds = new Set(nonWithdrawn.flatMap((requirement) => requirement.derivedFrom))
  const approvedScenarios = spec.scenarios.filter((scenario) => !scenario.dropReason)
  const approvedConstraints = spec.constraints.filter((constraint) => constraint.ruling === 'approved' || constraint.ruling === 'rewritten')
  const approvedItems = [...approvedScenarios, ...approvedConstraints]
  const moved = spec.requirements.filter((requirement) => requirementMoved(state, requirement))
  const warnings = scopeWarnings(state, spec)
  const noDisputes = Object.keys(state.disputes).length === 0
  const noReopened = !spec.scenarios.some((scenario) => scenario.reopened)
  return [
    {
      id: 'derivation',
      label: 'Derive at least one requirement from every approved scenario and constraint',
      done: approvedItems.filter((item) => derivedIds.has(item.id)).length,
      total: approvedItems.length,
    },
    { id: 'move-reasons', label: 'Give a reason for every changed placement', done: moved.filter((requirement) => state.moveReasons[requirement.id]?.trim()).length, total: moved.length },
    { id: 'scope-warnings', label: 'Resolve scope warnings, conflicts, and orphaned dependencies', done: warnings.length === 0 ? 1 : 0, total: 1 },
    { id: 'disputes', label: 'Resolve every dispute and re-approve every reopened scenario', done: noDisputes && noReopened ? 1 : 0, total: 1 },
  ]
}

export function decisionRecord(state: ReviewState, spec: LogicSpec): DecisionRecord {
  const placements = spec.requirements.flatMap((requirement) => {
    if (!requirementMoved(state, requirement)) return []
    const to = effectivePlacement(state, requirement)
    return [{
      id: requirement.id,
      from: placementInSpec(requirement),
      to,
      condition: to === 'conditional' ? effectiveCondition(state, requirement) : null,
      reason: state.moveReasons[requirement.id] ?? '',
    }]
  })
  const warnings = scopeWarnings(state, spec)
  return {
    stage: spec.stage,
    verdict: state.verdict ?? null,
    verdictNote: state.verdictNote,
    signedAt: state.signedAt ?? null,
    scenarios: spec.scenarios.map((scenario) => ({
      id: scenario.id,
      approved: Boolean(state.scenarioApproved[scenario.id]),
      dropped: state.scenarioDrops[scenario.id] ?? null,
      then: scenarioThen(state, scenario),
      changesSpec: scenarioThen(state, scenario) !== scenario.then,
    })),
    constraints: spec.constraints.map((constraint) => {
      const ruling = state.constraintRulings[constraint.id]
      return { id: constraint.id, ruling: ruling?.ruling ?? null, text: ruling?.text ?? '', reason: ruling?.reason ?? '' }
    }),
    assumptions: spec.assumptions.map((item) => ({ id: item.id, ruling: state.assumptions[item.id]?.ruling ?? null, note: state.assumptions[item.id]?.note ?? '' })),
    blindSpots: activeBlindSpots(state, spec).map((item) => ({ id: item.id, accepted: Boolean(state.blindSpots[item.id]?.accepted), note: state.blindSpots[item.id]?.note ?? '' })),
    placements,
    disputes: Object.entries(state.disputes).map(([requirementId, dispute]) => ({ requirementId, ...dispute })),
    scenarioRequests: pendingScenarioRequests(state, spec),
    researchRequests: pendingResearchRequests(state, spec),
    openWarnings: warnings,
  }
}

export function useViewerMode(): 'light' | 'dark' | 'system' {
  const read = (): 'light' | 'dark' | 'system' => {
    const theme = document.documentElement.dataset.theme
    return theme === 'light' || theme === 'dark' ? theme : 'system'
  }
  const [mode, setMode] = useState(read)
  useEffect(() => {
    const observer = new MutationObserver(() => setMode(read()))
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
    return () => observer.disconnect()
  }, [])
  return mode
}

export function requestId(prefix: string): string {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`
}

export function localStamp(date: Date): string {
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}T${pad(date.getHours())}${pad(date.getMinutes())}${pad(date.getSeconds())}`
}

export function placedRequirements(spec: LogicSpec, state: ReviewState): { requirement: Requirement; placement: Placement }[] {
  return spec.requirements.map((requirement) => ({ requirement, placement: effectivePlacement(state, requirement) }))
}

export type TraceRow = { id: string; kind: 'scenario' | 'constraint'; text: string; requirementIds: string[]; status: 'covered' | 'gap' }
export type NonGoalRow = { id: string; kind: 'scenario' | 'constraint'; text: string; reason: string }

/** `CONTRACT:` one row per approved stage-1 item, linking to the non-withdrawn requirements derived from it (see Trace matrix). */
export function traceMatrix(spec: LogicSpec): { rows: TraceRow[]; nonGoals: NonGoalRow[] } {
  const nonWithdrawn = spec.requirements.filter((requirement) => requirementStatus(requirement, spec) !== 'withdrawn')
  const derivedRequirementIds = (itemId: string) => nonWithdrawn.filter((requirement) => requirement.derivedFrom.includes(itemId)).map((requirement) => requirement.id)
  const rows: TraceRow[] = []
  const nonGoals: NonGoalRow[] = []
  for (const scenario of spec.scenarios) {
    if (scenario.dropReason) {
      nonGoals.push({ id: scenario.id, kind: 'scenario', text: scenario.then, reason: scenario.dropReason })
      continue
    }
    const requirementIds = derivedRequirementIds(scenario.id)
    rows.push({ id: scenario.id, kind: 'scenario', text: scenario.then, requirementIds, status: requirementIds.length > 0 ? 'covered' : 'gap' })
  }
  for (const constraint of spec.constraints) {
    if (constraint.ruling === 'rejected') {
      nonGoals.push({ id: constraint.id, kind: 'constraint', text: constraint.text, reason: constraint.rejectReason ?? '' })
      continue
    }
    if (constraint.ruling !== 'approved' && constraint.ruling !== 'rewritten') continue
    const requirementIds = derivedRequirementIds(constraint.id)
    rows.push({ id: constraint.id, kind: 'constraint', text: constraint.text, requirementIds, status: requirementIds.length > 0 ? 'covered' : 'gap' })
  }
  return { rows, nonGoals }
}

export type WithdrawnRequirement = { requirement: Requirement; scenarios: Scenario[] }

/** `CONTRACT:` withdrawn requirements are excluded from the board; the page lists them here with the reopened scenario(s) they came from. */
export function withdrawnRequirements(spec: LogicSpec): WithdrawnRequirement[] {
  return spec.requirements
    .filter((requirement) => requirementStatus(requirement, spec) === 'withdrawn')
    .map((requirement) => ({
      requirement,
      scenarios: requirement.derivedFrom
        .map((id) => spec.scenarios.find((scenario) => scenario.id === id))
        .filter((scenario): scenario is Scenario => Boolean(scenario)),
    }))
}
