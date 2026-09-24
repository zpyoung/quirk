import { useEffect, useState } from 'react'
import type {
  Assumption,
  AssumptionRuling,
  BlindSpot,
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

export type ViewId = 'board' | 'risks' | 'scenarios' | 'coverage' | 'heatmap' | 'story-map' | 'states' | 'spec' | 'sign-off'
export type TabSpec = { id: ViewId; label: string }
export type Snapshot = { state: ReviewState; seen: Record<string, string>; lastExportUpdatedAt: string | null; renderId: string | null; storageOk: boolean }
export type PayloadResult = { payload: LogicSpecPayload | null; error: string | null }
export type ReviewGate = { id: string; label: string; done: number; total: number }
export type Update = (recipe: (state: ReviewState) => ReviewState, reviewedItemId?: string) => void

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

export function emptyState(): ReviewState {
  return {
    placements: {},
    conditions: {},
    moveReasons: {},
    notes: {},
    assumptions: {},
    blindSpots: {},
    scenarioOutcomes: {},
    scenarioApproved: {},
    scenarioRequests: [],
    researchRequests: [],
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
  return (
    isObject(value.placements) && Object.values(value.placements).every(isPlacement) &&
    isObject(value.conditions) && Object.values(value.conditions).every(isCondition) &&
    isStringMap(value.moveReasons) &&
    isStringMap(value.notes) &&
    isObject(value.assumptions) && Object.values(value.assumptions).every((decision) =>
      isObject(decision) && typeof decision.note === 'string' && (decision.ruling === undefined || isRuling(decision.ruling))) &&
    isObject(value.blindSpots) && Object.values(value.blindSpots).every((decision) =>
      isObject(decision) && typeof decision.accepted === 'boolean' && typeof decision.note === 'string') &&
    isObject(value.scenarioOutcomes) && Object.values(value.scenarioOutcomes).every((outcome) =>
      isObject(outcome) && typeof outcome.choice === 'string' &&
      (outcome.choice === 'spec' || outcome.choice === 'custom' || /^alt-\d+$/.test(outcome.choice)) &&
      typeof outcome.custom === 'string') &&
    isObject(value.scenarioApproved) && Object.values(value.scenarioApproved).every((approved) => typeof approved === 'boolean') &&
    Array.isArray(value.scenarioRequests) && value.scenarioRequests.every((request) =>
      isObject(request) && typeof request.id === 'string' && typeof request.text === 'string' && typeof request.requestedAt === 'string') &&
    Array.isArray(value.researchRequests) && value.researchRequests.every((request) =>
      isObject(request) && typeof request.id === 'string' && typeof request.blindSpotId === 'string' &&
      typeof request.question === 'string' && typeof request.requestedAt === 'string') &&
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
    value.schemaVersion === 1 &&
    typeof value.slug === 'string' &&
    (slug === undefined || value.slug === slug) &&
    typeof value.renderId === 'string' &&
    typeof value.exportedAt === 'string' &&
    typeof value.signed === 'boolean' &&
    isStringMap(value.seen) &&
    isReviewState(value.state) &&
    isObject(value.record)
  )
}

export function isLogicSpec(value: unknown): value is LogicSpec {
  if (!isObject(value) || value.schemaVersion !== 1 || typeof value.title !== 'string' || typeof value.status !== 'string') return false
  if (!Array.isArray(value.requirements) || !Array.isArray(value.conflicts) || !Array.isArray(value.assumptions) ||
      !Array.isArray(value.blindSpots) || !Array.isArray(value.scenarios) || !Array.isArray(value.research) ||
      !Array.isArray(value.amendments) || !isObject(value.sections)) return false
  if (value.requirements.some((item) => !isObject(item) || typeof item.id !== 'string' || typeof item.area !== 'string' ||
      typeof item.text !== 'string' || typeof item.summary !== 'string' || typeof item.detail !== 'string' ||
      (item.scope !== 'in' && item.scope !== 'out') || !Array.isArray(item.dependsOn) ||
      !item.dependsOn.every((id) => typeof id === 'string') ||
      !['min', 'i3', 'i2', 'i1'].includes(String(item.group)) ||
      !['you-chose', 'you-recommended', 'claude'].includes(String(item.provenance)) ||
      (item.certainty !== null && !['confirmed', 'assumed', 'unverified'].includes(String(item.certainty))))) return false
  if (value.assumptions.some((item) => !isObject(item) || typeof item.id !== 'string' || typeof item.claim !== 'string' ||
      typeof item.basis !== 'string' || typeof item.ifWrong !== 'string' || !Array.isArray(item.affects) ||
      typeof item.meaning !== 'string' || typeof item.check !== 'string' || typeof item.checkCost !== 'string')) return false
  if (value.blindSpots.some((item) => !isObject(item) || typeof item.id !== 'string' || typeof item.title !== 'string' ||
      typeof item.detail !== 'string' || !Array.isArray(item.sources))) return false
  if (value.scenarios.some((item) => !isObject(item) || typeof item.id !== 'string' || typeof item.given !== 'string' ||
      typeof item.when !== 'string' || typeof item.then !== 'string' || !Array.isArray(item.alternatives) ||
      typeof item.explanation !== 'string' || !Array.isArray(item.refs))) return false
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
    placements: { ...state.placements },
    conditions: { ...state.conditions },
    moveReasons: { ...state.moveReasons },
    notes: { ...state.notes },
    assumptions: Object.fromEntries(Object.entries(state.assumptions).map(([id, decision]) => [id, { ...decision }])),
    blindSpots: Object.fromEntries(Object.entries(state.blindSpots).map(([id, decision]) => [id, { ...decision }])),
    scenarioOutcomes: Object.fromEntries(Object.entries(state.scenarioOutcomes).map(([id, outcome]) => [id, { ...outcome }])),
    scenarioApproved: { ...state.scenarioApproved },
    scenarioRequests: state.scenarioRequests.map((request) => ({ ...request })),
    researchRequests: state.researchRequests.map((request) => ({ ...request })),
  }
}

export function itemIds(spec: LogicSpec): string[] {
  return [...spec.requirements, ...spec.assumptions, ...spec.blindSpots, ...spec.scenarios].map((item) => item.id)
}

export function changedItemIds(spec: LogicSpec, hashes: Record<string, string>, seen: Record<string, string>): string[] {
  return itemIds(spec).filter((id) => seen[id] !== hashes[id])
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
  const requirementIds = new Set(spec.requirements.map((item) => item.id))
  const assumptionIds = new Set(spec.assumptions.map((item) => item.id))
  const blindSpotIds = new Set(spec.blindSpots.map((item) => item.id))
  const scenarioIds = new Set(spec.scenarios.map((item) => item.id))
  const allItemIds = new Set([...requirementIds, ...assumptionIds, ...blindSpotIds, ...scenarioIds])
  const changedIds = changedItemIds(spec, hashes, seen)
  const currentSeen = retainItemIds(seen, allItemIds)
  const next = cloneState(state)
  let stateChanged = false
  for (const id of changedIds) {
    stateChanged ||= Object.hasOwn(next.placements, id) || Object.hasOwn(next.conditions, id) ||
      Object.hasOwn(next.moveReasons, id) || Object.hasOwn(next.notes, id) ||
      Object.hasOwn(next.assumptions, id) || Object.hasOwn(next.blindSpots, id) ||
      Object.hasOwn(next.scenarioOutcomes, id) || Object.hasOwn(next.scenarioApproved, id)
    delete next.placements[id]
    delete next.conditions[id]
    delete next.moveReasons[id]
    delete next.notes[id]
    delete next.assumptions[id]
    delete next.blindSpots[id]
    delete next.scenarioOutcomes[id]
    delete next.scenarioApproved[id]
  }
  const originalCounts = [
    Object.keys(next.placements).length,
    Object.keys(next.conditions).length,
    Object.keys(next.moveReasons).length,
    Object.keys(next.notes).length,
    Object.keys(next.assumptions).length,
    Object.keys(next.blindSpots).length,
    Object.keys(next.scenarioOutcomes).length,
    Object.keys(next.scenarioApproved).length,
    next.researchRequests.length,
  ]
  next.placements = retainItemIds(next.placements, requirementIds)
  next.conditions = retainItemIds(next.conditions, requirementIds)
  next.moveReasons = retainItemIds(next.moveReasons, requirementIds)
  next.notes = retainItemIds(next.notes, allItemIds)
  next.assumptions = retainItemIds(next.assumptions, assumptionIds)
  next.blindSpots = retainItemIds(next.blindSpots, blindSpotIds)
  next.scenarioOutcomes = retainItemIds(next.scenarioOutcomes, scenarioIds)
  next.scenarioApproved = retainItemIds(next.scenarioApproved, scenarioIds)
  next.researchRequests = next.researchRequests.filter((request) => blindSpotIds.has(request.blindSpotId))
  const retainedCounts = [
    Object.keys(next.placements).length,
    Object.keys(next.conditions).length,
    Object.keys(next.moveReasons).length,
    Object.keys(next.notes).length,
    Object.keys(next.assumptions).length,
    Object.keys(next.blindSpots).length,
    Object.keys(next.scenarioOutcomes).length,
    Object.keys(next.scenarioApproved).length,
    next.researchRequests.length,
  ]
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
  const prior = payload.priorDecisions && isDecisionExport(payload.priorDecisions, payload.slug)
    ? {
        state: payload.priorDecisions.state,
        seen: payload.priorDecisions.seen,
        lastExportUpdatedAt: payload.priorDecisions.state.updatedAt,
        renderId: payload.priorDecisions.renderId,
      }
    : null
  let selected = local ?? prior
  if (local && prior && laterThan(prior.state.updatedAt, local.state.updatedAt)) selected = prior
  if (!selected) selected = { state: emptyState(), seen: {}, lastExportUpdatedAt: null, renderId: null }
  const carried = carryOver(selected.state, selected.seen, payload.spec, payload.itemHashes, selected.renderId, payload.renderId)
  return { ...carried, lastExportUpdatedAt: selected.lastExportUpdatedAt, renderId: payload.renderId, storageOk }
}

export function placementInSpec(requirement: Requirement): Placement {
  if (requirement.scope === 'out') return 'out'
  return requirement.condition ? 'conditional' : 'in'
}

export function effectivePlacement(state: ReviewState, requirement: Requirement): Placement | undefined {
  if (requirement.provenance === 'claude' && !state.placements[requirement.id]) return undefined
  return state.placements[requirement.id] ?? placementInSpec(requirement)
}

export function effectiveCondition(state: ReviewState, requirement: Requirement): ScopeCondition {
  return state.conditions[requirement.id] ?? requirement.condition ?? 'under-10'
}

export function requirementMoved(state: ReviewState, requirement: Requirement): boolean {
  const current = effectivePlacement(state, requirement)
  if (current === undefined) return false
  const original = placementInSpec(requirement)
  return current !== original || (current === 'conditional' && effectiveCondition(state, requirement) !== requirement.condition)
}

export function scopeWarnings(state: ReviewState, spec: LogicSpec): string[] {
  const requirements = new Map(spec.requirements.map((requirement) => [requirement.id, requirement]))
  const warnings: string[] = []
  for (const requirement of spec.requirements) {
    const placement = effectivePlacement(state, requirement)
    if (placement === undefined || placement === 'out') continue
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
      } else if (dependencyPlacement !== undefined) {
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
    if (firstPlacement && firstPlacement !== 'out' && secondPlacement && secondPlacement !== 'out') {
      warnings.push(`${firstId} and ${secondId} conflict while both are in scope.`)
    }
  }
  return warnings
}

export function activeBlindSpots(state: ReviewState, spec: LogicSpec): BlindSpot[] {
  const requirements = new Map(spec.requirements.map((requirement) => [requirement.id, requirement]))
  return spec.blindSpots.filter((spot) => {
    const allSourcesInScope = spot.sources.every((id) => {
      const requirement = requirements.get(id)
      const placement = requirement ? effectivePlacement(state, requirement) : undefined
      return placement !== undefined && placement !== 'out'
    })
    if (!allSourcesInScope) return false
    if (!spot.resolvedBy) return true
    const resolver = requirements.get(spot.resolvedBy)
    return !resolver || effectivePlacement(state, resolver) !== 'in'
  })
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

export function gateList(state: ReviewState, spec: LogicSpec): ReviewGate[] {
  const queue = spec.requirements.filter((requirement) => requirement.provenance === 'claude')
  const activeSpots = activeBlindSpots(state, spec)
  const warnings = scopeWarnings(state, spec)
  const moved = spec.requirements.filter((requirement) => requirementMoved(state, requirement))
  const pending = pendingScenarioRequests(state, spec)
  const ruled = (assumption: Assumption) => {
    const decision = state.assumptions[assumption.id]
    return Boolean(decision?.ruling && (decision.ruling === 'build-on' || decision.note.trim()))
  }
  return [
    { id: 'queue', label: 'Place every item Claude decided on its own', done: queue.filter((item) => Boolean(state.placements[item.id])).length, total: queue.length },
    { id: 'assumptions', label: 'Rule on every assumption; explain rulings other than build on', done: spec.assumptions.filter(ruled).length, total: spec.assumptions.length },
    { id: 'blind-spots', label: 'Accept every active blind spot in your own words', done: activeSpots.filter((spot) => state.blindSpots[spot.id]?.accepted && state.blindSpots[spot.id]?.note.trim()).length, total: activeSpots.length },
    { id: 'scenarios', label: 'Approve every scenario and resolve pending requests', done: spec.scenarios.filter((scenario) => state.scenarioApproved[scenario.id]).length, total: spec.scenarios.length + pending.length },
    { id: 'move-reasons', label: 'Give a reason for every changed placement', done: moved.filter((requirement) => state.moveReasons[requirement.id]?.trim()).length, total: moved.length },
    { id: 'scope-warnings', label: 'Resolve scope warnings, conflicts, and orphaned dependencies', done: warnings.length === 0 ? 1 : 0, total: 1 },
  ]
}

export function decisionRecord(state: ReviewState, spec: LogicSpec): DecisionRecord {
  const placements = spec.requirements.flatMap((requirement) => {
    const to = effectivePlacement(state, requirement)
    if (!to || !requirementMoved(state, requirement)) return []
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
    verdict: state.verdict ?? null,
    verdictNote: state.verdictNote,
    signedAt: state.signedAt ?? null,
    placements,
    assumptions: spec.assumptions.map((item) => ({ id: item.id, ...(state.assumptions[item.id] ?? { note: '' }) })),
    blindSpots: activeBlindSpots(state, spec).map((item) => ({ id: item.id, accepted: Boolean(state.blindSpots[item.id]?.accepted), note: state.blindSpots[item.id]?.note ?? '' })),
    scenarios: spec.scenarios.map((scenario) => ({
      id: scenario.id,
      approved: Boolean(state.scenarioApproved[scenario.id]),
      then: scenarioThen(state, scenario),
      changesSpec: scenarioThen(state, scenario) !== scenario.then,
    })),
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


export function coverageGaps(spec: LogicSpec, state: ReviewState) {
  const inScope = spec.requirements.filter((requirement) => {
    const placement = effectivePlacement(state, requirement)
    return placement !== undefined && placement !== 'out'
  })
  const covered = new Set(spec.scenarios.flatMap((scenario) => scenario.refs))
  const gaps: { id: string; text: string; view: ViewId }[] = inScope.filter((requirement) => !covered.has(requirement.id)).map((requirement) => ({ id: `req-${requirement.id}`, text: `${requirement.id} has no scenario coverage`, view: 'scenarios' }))
  spec.assumptions.filter((assumption) => !state.assumptions[assumption.id]?.ruling).forEach((assumption) => gaps.push({ id: `assumption-${assumption.id}`, text: `${assumption.id} still needs a ruling`, view: 'risks' }))
  activeBlindSpots(state, spec).filter((spot) => !state.blindSpots[spot.id]?.accepted || !state.blindSpots[spot.id]?.note.trim()).forEach((spot) => gaps.push({ id: `blind-${spot.id}`, text: `${spot.id} still needs written acceptance`, view: 'risks' }))
  return gaps
}

export function placedRequirements(spec: LogicSpec, state: ReviewState): { requirement: Requirement; placement: Placement }[] {
  const placed: { requirement: Requirement; placement: Placement }[] = []
  for (const requirement of spec.requirements) {
    const placement = effectivePlacement(state, requirement)
    if (placement !== undefined) placed.push({ requirement, placement })
  }
  return placed
}
