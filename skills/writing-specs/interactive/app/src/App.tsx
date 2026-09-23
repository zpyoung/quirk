import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Markdown, type MarkdownComponents } from '@astryxdesign/core/Markdown'
import { Theme } from '@astryxdesign/core/theme'
import { neutralTheme } from '@astryxdesign/theme-neutral/built'
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
  ScenarioChoice,
  ScopeCondition,
  StateMachine,
  StateMachineTransition,
} from './spec-types'
import { layoutStateMachine, type MachineLayout } from './layout'
import '@astryxdesign/theme-neutral/theme.css'
import './index.css'

type ViewId = 'board' | 'risks' | 'scenarios' | 'coverage' | 'heatmap' | 'story-map' | 'states' | 'spec' | 'sign-off'
type TabSpec = { id: ViewId; label: string }
type Snapshot = { state: ReviewState; seen: Record<string, string>; lastExportUpdatedAt: string | null; renderId: string | null; storageOk: boolean }
type PayloadResult = { payload: LogicSpecPayload | null; error: string | null }
type ReviewGate = { id: string; label: string; done: number; total: number }
type Update = (recipe: (state: ReviewState) => ReviewState, reviewedItemId?: string) => void

const PAYLOAD_ID = 'quirk-logic-spec-payload'
const EXPORT_KIND = 'quirk-logic-spec-decisions'
const CHOICE_LABEL: Record<Placement, string> = { in: 'In scope', conditional: 'Conditionally in scope', out: 'Out of scope' }
const CONDITION_LABEL: Record<ScopeCondition, string> = {
  'no-code': 'No extra code required',
  'under-10': 'Under 10 lines of code',
  'under-30': 'Under 30 lines of code',
}
const RULINGS: { value: AssumptionRuling; label: string }[] = [
  { value: 'build-on', label: 'Build on it' },
  { value: 'verify-first', label: 'Verify first' },
  { value: 'wrong', label: 'Treat it as wrong' },
]
const CERTAINTIES = ['confirmed', 'assumed', 'unverified'] as const
const GROUPS = ['min', 'i3', 'i2', 'i1'] as const
const GROUP_LABEL: Record<(typeof GROUPS)[number], string> = {
  min: 'Minimum',
  i3: 'Impact 3',
  i2: 'Impact 2',
  i1: 'Impact 1',
}

function emptyState(): ReviewState {
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

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isStringMap(value: unknown): value is Record<string, string> {
  return isObject(value) && Object.values(value).every((item) => typeof item === 'string')
}

function isReviewState(value: unknown): value is ReviewState {
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

function isDecisionExport(value: unknown, slug?: string): value is Export {
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

function isLogicSpec(value: unknown): value is LogicSpec {
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

function isPayload(value: unknown): value is LogicSpecPayload {
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

function readPayload(): PayloadResult {
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

function laterThan(a: string, b: string): boolean {
  return (Date.parse(a) || 0) > (Date.parse(b) || 0)
}

function nextTimestamp(previous?: string): string {
  const now = Date.now()
  const previousTime = previous ? Date.parse(previous) || 0 : 0
  return new Date(Math.max(now, previousTime + 1)).toISOString()
}

function cloneState(state: ReviewState): ReviewState {
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

function itemIds(spec: LogicSpec): string[] {
  return [...spec.requirements, ...spec.assumptions, ...spec.blindSpots, ...spec.scenarios].map((item) => item.id)
}

function changedItemIds(spec: LogicSpec, hashes: Record<string, string>, seen: Record<string, string>): string[] {
  return itemIds(spec).filter((id) => seen[id] !== hashes[id])
}

function retainItemIds<T>(values: Record<string, T>, allowed: Set<string>): Record<string, T> {
  const retained: Record<string, T> = {}
  for (const [id, value] of Object.entries(values)) {
    if (allowed.has(id)) retained[id] = value
  }
  return retained
}

function carryOver(
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

function readLocalSnapshot(key: string): Omit<Snapshot, 'storageOk'> | null {
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

function bootstrap(payload: LogicSpecPayload): Snapshot {
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

function placementInSpec(requirement: Requirement): Placement {
  if (requirement.scope === 'out') return 'out'
  return requirement.condition ? 'conditional' : 'in'
}

function effectivePlacement(state: ReviewState, requirement: Requirement): Placement | undefined {
  if (requirement.provenance === 'claude' && !state.placements[requirement.id]) return undefined
  return state.placements[requirement.id] ?? placementInSpec(requirement)
}

function effectiveCondition(state: ReviewState, requirement: Requirement): ScopeCondition {
  return state.conditions[requirement.id] ?? requirement.condition ?? 'under-10'
}

function requirementMoved(state: ReviewState, requirement: Requirement): boolean {
  const current = effectivePlacement(state, requirement)
  if (current === undefined) return false
  const original = placementInSpec(requirement)
  return current !== original || (current === 'conditional' && effectiveCondition(state, requirement) !== requirement.condition)
}

function scopeWarnings(state: ReviewState, spec: LogicSpec): string[] {
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

function activeBlindSpots(state: ReviewState, spec: LogicSpec): BlindSpot[] {
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

function pendingScenarioRequests(state: ReviewState, spec: LogicSpec) {
  const converted = new Set(spec.scenarios.flatMap((scenario) => scenario.requestId ? [scenario.requestId] : []))
  return state.scenarioRequests.filter((request) => !converted.has(request.id))
}
function pendingResearchRequests(state: ReviewState, spec: LogicSpec) {
  const answered = new Set(spec.research.map((finding) => finding.requestId))
  return state.researchRequests.filter((request) => !answered.has(request.id))
}

function scenarioThen(state: ReviewState, scenario: Scenario): string {
  const outcome = state.scenarioOutcomes[scenario.id]
  if (!outcome || outcome.choice === 'spec') return scenario.then
  if (outcome.choice === 'custom') return outcome.custom.trim() || scenario.then
  const index = Number(outcome.choice.slice(4))
  return scenario.alternatives[index] ?? scenario.then
}

function gateList(state: ReviewState, spec: LogicSpec): ReviewGate[] {
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

function decisionRecord(state: ReviewState, spec: LogicSpec): DecisionRecord {
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

function useViewerMode(): 'light' | 'dark' | 'system' {
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

function requestId(prefix: string): string {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`
}

function localStamp(date: Date): string {
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}T${pad(date.getHours())}${pad(date.getMinutes())}${pad(date.getSeconds())}`
}

function isChanged(id: string, changedIds: Set<string>) {
  return changedIds.has(id) ? <span data-kind="changed">Changed since you reviewed</span> : null
}

const OFFLINE_MARKDOWN_COMPONENTS: MarkdownComponents = {
  image: ({ alt }) => <span>{alt ? `Image omitted in offline review: ${alt}` : 'Image omitted in offline review.'}</span>,
}

function ClaudeCopy({ children }: { children: string }) {
  return <div><span data-kind="attribution">Claude wrote this</span><Markdown components={OFFLINE_MARKDOWN_COMPONENTS} contentWidth="100%">{children}</Markdown></div>
}

function RequirementCard({ requirement, state, update, changedIds }: { requirement: Requirement; state: ReviewState; update: Update; changedIds: Set<string> }) {
  const placement = effectivePlacement(state, requirement)
  const baseline = placementInSpec(requirement)
  const moved = requirementMoved(state, requirement)
  const selected = placement ?? ''
  const condition = effectiveCondition(state, requirement)
  const setPlacement = (value: Placement | '') => {
    update((current) => {
      const placements = { ...current.placements }
      const conditions = { ...current.conditions }
      if (value === '') {
        delete placements[requirement.id]
      } else if (requirement.provenance === 'claude' || value !== baseline) {
        placements[requirement.id] = value
      } else {
        delete placements[requirement.id]
      }
      if (value === 'conditional') {
        conditions[requirement.id] = current.conditions[requirement.id] ?? requirement.condition ?? 'under-10'
      } else {
        delete conditions[requirement.id]
      }
      return { ...current, placements, conditions }
    }, requirement.id)
  }
  return (
    <article data-kind="requirement" data-out={placement === 'out'}>
      <header>
        <p><strong>{requirement.id}</strong> · {requirement.area} {isChanged(requirement.id, changedIds)}</p>
        <p><span data-kind="attribution">Claude wrote this</span></p>
        <h3>{requirement.summary}</h3>
        <p><strong>Claude's group:</strong> {GROUP_LABEL[requirement.group]} · <strong>Origin:</strong> {requirement.provenance}</p>
        <p><strong>Claude's suggested placement:</strong> {CHOICE_LABEL[baseline]}{requirement.condition ? ` · ${CONDITION_LABEL[requirement.condition]}` : ''}</p>
      </header>
      <p><strong>Requirement:</strong> {requirement.text}</p>
      <ClaudeCopy>{requirement.detail}</ClaudeCopy>
      {requirement.rationale ? <ClaudeCopy>{requirement.rationale}</ClaudeCopy> : null}
      {requirement.question ? <p><strong>Asked during brainstorming:</strong> {requirement.question}</p> : null}
      <p><strong>Certainty:</strong> {requirement.certainty ?? 'not specified'} · <strong>Depends on:</strong> {requirement.dependsOn.length ? requirement.dependsOn.join(', ') : 'none'}</p>
      <label>
        Your placement
        <select aria-label={`Placement for ${requirement.id}`} value={selected} onChange={(event) => setPlacement(event.target.value as Placement | '')}>
          {requirement.provenance === 'claude' && !placement ? <option value="">Choose a placement…</option> : null}
          <option value="in">In scope</option>
          <option value="conditional">Conditionally in scope</option>
          <option value="out">Out of scope</option>
        </select>
      </label>
      {placement === 'conditional' ? (
        <label>
          Include only if
          <select
            aria-label={`Condition for ${requirement.id}`}
            value={condition}
            onChange={(event) => update((current) => ({ ...current, conditions: { ...current.conditions, [requirement.id]: event.target.value as ScopeCondition } }), requirement.id)}
          >
            {Object.entries(CONDITION_LABEL).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
      ) : null}
      {moved ? (
        <label>
          Why did you change this placement?
          <textarea
            aria-label={`Reason for changing ${requirement.id}`}
            rows={2}
            value={state.moveReasons[requirement.id] ?? ''}
            onChange={(event) => update((current) => ({ ...current, moveReasons: { ...current.moveReasons, [requirement.id]: event.target.value } }), requirement.id)}
          />
        </label>
      ) : null}
      <label>
        Your notes
        <textarea
          aria-label={`Notes for ${requirement.id}`}
          rows={2}
          value={state.notes[requirement.id] ?? ''}
          onChange={(event) => update((current) => ({ ...current, notes: { ...current.notes, [requirement.id]: event.target.value } }), requirement.id)}
        />
      </label>
    </article>
  )
}

function ScopeBoard({ spec, state, update, changedIds }: { spec: LogicSpec; state: ReviewState; update: Update; changedIds: Set<string> }) {
  const warnings = scopeWarnings(state, spec)
  const requirements = spec.requirements
  const queue = requirements.filter((item) => item.provenance === 'claude' && !state.placements[item.id])
  const groups: { placement: Placement; title: string }[] = [
    { placement: 'in', title: 'In scope' },
    { placement: 'conditional', title: 'Conditionally in scope' },
    { placement: 'out', title: 'Out of scope' },
  ]
  return (
    <section>
      <h2>Scope board</h2>
      <p>Decide where every Claude-added requirement belongs. Nothing is preselected for those items. Changes from the logic spec's placement need a reason; out-of-scope choices can expose dependency or conflict warnings.</p>
      {queue.length ? <section aria-labelledby="queue-title"><h3 id="queue-title">Awaiting your call ({queue.length})</h3>{queue.map((item) => <RequirementCard key={item.id} requirement={item} state={state} update={update} changedIds={changedIds} />)}</section> : null}
      {warnings.length ? <aside role="alert" data-kind="warning"><h3>Resolve scope warnings</h3><ul>{warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul></aside> : null}
      {groups.map(({ placement, title }) => {
        const items = requirements.filter((item) => effectivePlacement(state, item) === placement && !(item.provenance === 'claude' && !state.placements[item.id]))
        return <section key={placement} aria-labelledby={`scope-${placement}`}><h3 id={`scope-${placement}`}>{title} ({items.length})</h3>{items.length ? items.map((item) => <RequirementCard key={item.id} requirement={item} state={state} update={update} changedIds={changedIds} />) : <p>No requirements here.</p>}</section>
      })}
    </section>
  )
}

function RiskViews({ spec, state, update, changedIds }: { spec: LogicSpec; state: ReviewState; update: Update; changedIds: Set<string> }) {
  const activeIds = new Set(activeBlindSpots(state, spec).map((spot) => spot.id))
  return (
    <section>
      <h2>Risks</h2>
      <p>Rule on every assumption. Accept active blind spots only in your own words. Research requests travel back to Claude in your decision export.</p>
      <section><h3>Assumptions</h3>{spec.assumptions.length ? spec.assumptions.map((assumption) => {
        const current = state.assumptions[assumption.id] ?? { ruling: undefined, note: '' }
        return (
          <article key={assumption.id}>
            <p><strong>{assumption.id} · {assumption.certainty}</strong> {isChanged(assumption.id, changedIds)}</p>
            <h3>{assumption.claim}</h3>
            <p><strong>Basis:</strong> {assumption.basis}</p>
            <ClaudeCopy>{assumption.meaning}</ClaudeCopy>
            <p><strong>If wrong:</strong> {assumption.ifWrong}</p>
            <p><strong>Requirements affected:</strong> {assumption.affects.join(', ') || 'none'}</p>
            <ClaudeCopy>{assumption.check}</ClaudeCopy>
            <p><strong>Check cost:</strong> {assumption.checkCost}</p>
            <fieldset>
              <legend>Your ruling</legend>
              {RULINGS.map((ruling) => <label key={ruling.value}><input type="radio" name={`ruling-${assumption.id}`} checked={current.ruling === ruling.value} onChange={() => update((previous) => ({ ...previous, assumptions: { ...previous.assumptions, [assumption.id]: { ...previous.assumptions[assumption.id], ruling: ruling.value, note: previous.assumptions[assumption.id]?.note ?? '' } } }), assumption.id)} />{ruling.label}</label>)}
            </fieldset>
            {current.ruling && current.ruling !== 'build-on' ? <label>Why this ruling?<textarea rows={3} value={current.note} onChange={(event) => update((previous) => ({ ...previous, assumptions: { ...previous.assumptions, [assumption.id]: { ...previous.assumptions[assumption.id], ruling: current.ruling, note: event.target.value } } }), assumption.id)} /></label> : null}
          </article>
        )
      }) : <p>No assumptions.</p>}</section>
      <section><h3>Blind spots</h3>{spec.blindSpots.length ? spec.blindSpots.map((spot) => {
        const current = state.blindSpots[spot.id] ?? { accepted: false, note: '' }
        const findings = spec.research.filter((finding) => finding.blindSpotId === spot.id)
        const requests = pendingResearchRequests(state, spec).filter((request) => request.blindSpotId === spot.id)
        const active = activeIds.has(spot.id)
        return (
          <article key={spot.id}>
            <p><strong>{spot.id}</strong> {isChanged(spot.id, changedIds)} {active ? <span data-kind="active">Active</span> : <span>Inactive based on current scope</span>}</p>
            <h3>{spot.title}</h3>
            <ClaudeCopy>{spot.detail}</ClaudeCopy>
            <p><strong>Sources:</strong> {spot.sources.join(', ') || 'none'}{spot.resolvedBy ? ` · Resolved by ${spot.resolvedBy} when unconditionally in scope` : ''}</p>
            {active ? (
              <>
                <label><input type="checkbox" checked={current.accepted} onChange={(event) => update((previous) => ({ ...previous, blindSpots: { ...previous.blindSpots, [spot.id]: { ...previous.blindSpots[spot.id], accepted: event.target.checked, note: previous.blindSpots[spot.id]?.note ?? '' } } }), spot.id)} /> I accept this blind spot</label>
                <label>Your words about this blind spot<textarea rows={3} value={current.note} onChange={(event) => update((previous) => ({ ...previous, blindSpots: { ...previous.blindSpots, [spot.id]: { ...previous.blindSpots[spot.id], accepted: previous.blindSpots[spot.id]?.accepted ?? false, note: event.target.value } } }), spot.id)} /></label>
              </>
            ) : null}
            <ResearchRequestForm blindSpot={spot} update={update} />
            {requests.map((request) => <p key={request.id} data-kind="pending">Research requested: {request.question || '(no additional question)'} · {request.requestedAt}</p>)}
            {findings.map((finding) => <article key={finding.requestId}><h4>Research findings</h4><ClaudeCopy>{finding.summary}</ClaudeCopy><ClaudeCopy>{finding.detail}</ClaudeCopy><p>Answered {finding.answeredAt}</p></article>)}
          </article>
        )
      }) : <p>No blind spots.</p>}</section>
    </section>
  )
}

function ResearchRequestForm({ blindSpot, update }: { blindSpot: BlindSpot; update: Update }) {
  const [question, setQuestion] = useState('')
  const submit = () => {
    const text = question.trim()
    update((current) => ({
      ...current,
      researchRequests: [...current.researchRequests, { id: requestId('research'), blindSpotId: blindSpot.id, question: text, requestedAt: new Date().toISOString() }],
    }), blindSpot.id)
    setQuestion('')
  }
  return <fieldset><legend>Ask Claude to research this blind spot</legend><label>Research question<textarea rows={2} value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="What should Claude investigate?" /></label><button type="button" onClick={submit}>Request research</button></fieldset>
}

function ScenarioViews({ spec, state, update, changedIds }: { spec: LogicSpec; state: ReviewState; update: Update; changedIds: Set<string> }) {
  const [requestText, setRequestText] = useState('')
  const pending = pendingScenarioRequests(state, spec)
  const submitRequest = () => {
    const text = requestText.trim()
    if (!text) return
    update((current) => ({ ...current, scenarioRequests: [...current.scenarioRequests, { id: requestId('scenario'), text, requestedAt: new Date().toISOString() }] }))
    setRequestText('')
  }
  const setOutcome = (scenario: Scenario, choice: ScenarioChoice, custom: string) => update((current) => ({
    ...current,
    scenarioOutcomes: { ...current.scenarioOutcomes, [scenario.id]: { choice, custom } },
    scenarioApproved: { ...current.scenarioApproved, [scenario.id]: false },
  }), scenario.id)
  return (
    <section>
      <h2>Scenarios</h2>
      <p>Review each Given / When / Then scenario individually. Choose the spec's outcome, one of Claude's alternatives, or write your own. An edited outcome needs approval again.</p>
      {spec.scenarios.map((scenario) => {
        const outcome = state.scenarioOutcomes[scenario.id] ?? { choice: 'spec' as const, custom: '' }
        return (
          <article key={scenario.id}>
            <p><strong>{scenario.id}</strong> {scenario.requestId ? <span data-kind="active">Requested by you</span> : null} {isChanged(scenario.id, changedIds)}</p>
            <dl><dt>Given</dt><dd>{scenario.given}</dd><dt>When</dt><dd>{scenario.when}</dd><dt>Then</dt><dd>{scenario.then}</dd></dl>
            <ClaudeCopy>{scenario.explanation}</ClaudeCopy>
            <p><strong>Related requirements:</strong> {scenario.refs.join(', ') || 'none'}</p>
            <label>Outcome<select aria-label={`Outcome for ${scenario.id}`} value={outcome.choice} onChange={(event) => setOutcome(scenario, event.target.value as ScenarioChoice, outcome.custom)}>
              <option value="spec">Keep the spec's outcome</option>
              {scenario.alternatives.map((alternative, index) => <option key={`${scenario.id}-alt-${index}`} value={`alt-${index}`}>Claude's alternative: {alternative}</option>)}
              <option value="custom">Write my own outcome</option>
            </select></label>
            {outcome.choice === 'custom' ? <label>Your outcome<textarea rows={2} value={outcome.custom} onChange={(event) => setOutcome(scenario, 'custom', event.target.value)} /></label> : null}
            {scenarioThen(state, scenario) !== scenario.then ? <p data-kind="changed">This outcome changes the spec.</p> : null}
            <label><input type="checkbox" checked={Boolean(state.scenarioApproved[scenario.id])} disabled={outcome.choice === 'custom' && !outcome.custom.trim()} onChange={(event) => update((current) => ({ ...current, scenarioApproved: { ...current.scenarioApproved, [scenario.id]: event.target.checked } }), scenario.id)} /> I approve this scenario</label>
          </article>
        )
      })}
      <section><h3>Request another scenario</h3><p>Describe it in your own words. It stays pending until Claude converts it to a scenario in the spec.</p><label>Scenario request<textarea rows={3} value={requestText} onChange={(event) => setRequestText(event.target.value)} /></label><button type="button" disabled={!requestText.trim()} onClick={submitRequest}>Send request</button></section>
      <section><h3>Waiting for Claude ({pending.length})</h3>{pending.length ? <ul>{pending.map((request) => <li key={request.id}>{request.text} <button type="button" onClick={() => update((current) => ({ ...current, scenarioRequests: current.scenarioRequests.filter((item) => item.id !== request.id) }))}>Withdraw</button></li>)}</ul> : <p>No pending scenario requests.</p>}</section>
    </section>
  )
}

function coverageGaps(spec: LogicSpec, state: ReviewState) {
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

function CoverageView({ spec, state, onNavigate }: { spec: LogicSpec; state: ReviewState; onNavigate: (view: ViewId) => void }) {
  const gaps = coverageGaps(spec, state)
  return <section><h2>Coverage</h2><p>Informational gaps link to the review that can close them.</p>{gaps.length ? <ul>{gaps.map((gap) => <li key={gap.id}><button type="button" onClick={() => onNavigate(gap.view)}>{gap.text}</button></li>)}</ul> : <p>No coverage gaps.</p>}</section>
}

function placedRequirements(spec: LogicSpec, state: ReviewState): { requirement: Requirement; placement: Placement }[] {
  const placed: { requirement: Requirement; placement: Placement }[] = []
  for (const requirement of spec.requirements) {
    const placement = effectivePlacement(state, requirement)
    if (placement !== undefined) placed.push({ requirement, placement })
  }
  return placed
}

function ImpactCertaintyView({ spec, state }: { spec: LogicSpec; state: ReviewState }) {
  const requirements = placedRequirements(spec, state).filter(({ requirement }) => requirement.certainty !== null)
  return (
    <section>
      <h2>Impact × certainty</h2>
      <p>Requirements with certainty information, grouped by Claude's assessment.</p>
      <table>
        <thead><tr><th>Group</th>{CERTAINTIES.map((certainty) => <th key={certainty}>{certainty}</th>)}</tr></thead>
        <tbody>{GROUPS.map((group) => (
          <tr key={group}>
            <th scope="row">{GROUP_LABEL[group]}</th>
            {CERTAINTIES.map((certainty) => {
              const items = requirements.filter(({ requirement }) => requirement.group === group && requirement.certainty === certainty)
              return (
                <td key={certainty}>
                  {items.length ? <ul>{items.map(({ requirement, placement }) => (
                    <li key={requirement.id}><strong>{requirement.id}</strong> · <span data-kind="attribution">Claude wrote this</span> · {requirement.summary} ({CHOICE_LABEL[placement]})</li>
                  ))}</ul> : '—'}
                </td>
              )
            })}
          </tr>
        ))}</tbody>
      </table>
    </section>
  )
}

function StoryMapView({ spec, state }: { spec: LogicSpec; state: ReviewState }) {
  const storyMap = spec.views?.storyMap
  if (!storyMap) return null
  const requirements = placedRequirements(spec, state)
  return (
    <section>
      <h2>Story map</h2>
      <p>Journey areas and their spec coverage.</p>
      <div data-kind="story-map">
        {storyMap.journey.map((step) => {
          const items = requirements.filter(({ requirement }) => requirement.area === step.area)
          return (
            <article key={`${step.area}-${step.label}`}>
              <h3>{step.label}</h3>
              <p>{step.area}</p>
              {items.length ? <ul>{items.map(({ requirement, placement }) => (
                <li key={requirement.id}><strong>{requirement.id}</strong> · <span data-kind="attribution">Claude wrote this</span> · {requirement.summary} · {CHOICE_LABEL[placement]}</li>
              ))}</ul> : <p>No matching requirements.</p>}
            </article>
          )
        })}
      </div>
      <section><h3>Cross-cutting</h3><ul>{storyMap.crossCutting.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ul></section>
    </section>
  )
}

function StateMachineView({ machine, blindSpots }: { machine: StateMachine; blindSpots: BlindSpot[] }) {
  const [layout, setLayout] = useState<MachineLayout | null>(null)
  const [layoutError, setLayoutError] = useState(false)
  const [selectedTransition, setSelectedTransition] = useState<StateMachineTransition | null>(null)
  const [selectedBlindSpot, setSelectedBlindSpot] = useState<BlindSpot | null>(null)
  const transitionById = useMemo(() => new Map(machine.transitions.map((transition) => [transition.id, transition])), [machine])
  const blindSpotById = useMemo(() => new Map(blindSpots.map((spot) => [spot.id, spot])), [blindSpots])
  const openTransition = (transition: StateMachineTransition) => {
    setSelectedBlindSpot(null)
    setSelectedTransition(transition)
  }
  const openBlindSpot = (id: string) => {
    const spot = blindSpotById.get(id)
    if (!spot) return
    setSelectedTransition(null)
    setSelectedBlindSpot(spot)
  }
  const selectedBlindSpotId = selectedTransition?.blindSpot
  useEffect(() => {
    let alive = true
    setLayout(null)
    setLayoutError(false)
    void layoutStateMachine(machine).then((result) => { if (alive) setLayout(result) }).catch(() => { if (alive) { setLayout(null); setLayoutError(true) } })
    return () => { alive = false }
  }, [machine])
  return (
    <section>
      <h2>State machine</h2>
      <p>Computed layered layout with orthogonal transitions. Select a transition label or blind-spot chip for its details.</p>
      {!layout ? <p role="status">{layoutError ? 'Diagram layout unavailable. Use the transitions table below.' : 'Calculating diagram… The transitions table is available below.'}</p> : (
        <svg role="group" aria-label="State machine diagram" viewBox={`0 0 ${layout.width} ${layout.height}`}>
          <defs><marker id="quirk-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M 0 0 L 8 4 L 0 8 z" /></marker></defs>
          {layout.edges.map((edge) => {
            const transition = transitionById.get(edge.id)
            if (!transition) return null
            const blindSpotId = transition.blindSpot
            return (
              <g
                key={edge.id}
                role="button"
                tabIndex={0}
                aria-label={`Transition ${transition.short}`}
                onClick={() => openTransition(transition)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault()
                    openTransition(transition)
                  }
                }}
              >
                {edge.sections.map((section, index) => <path key={`${edge.id}-${index}`} d={section.path} markerEnd="url(#quirk-arrow)" />)}
                {edge.labels.map((label) => (
                  <g key={label.id} data-kind="edge-label" transform={`translate(${label.x} ${label.y})`}>
                    <rect width={label.width} height={label.height} rx="7" />
                    <text x={label.width / 2} y={label.height / 2 + 4} textAnchor="middle" textLength={Math.max(24, label.width - (blindSpotId ? 42 : 16))} lengthAdjust="spacingAndGlyphs">{transition.short}</text>
                    {blindSpotId ? (
                      <g
                        role="button"
                        tabIndex={0}
                        aria-label={`Blind spot ${blindSpotId}`}
                        data-kind="blind-chip"
                        transform={`translate(${label.width - 30} 3)`}
                        onClick={(event) => { event.stopPropagation(); openBlindSpot(blindSpotId) }}
                        onKeyDown={(event) => {
                          if (event.key === 'Enter' || event.key === ' ') {
                            event.stopPropagation()
                            event.preventDefault()
                            openBlindSpot(blindSpotId)
                          }
                        }}
                      >
                        <title>Open blind spot {blindSpotId}</title>
                        <rect width="24" height="20" rx="9" />
                        <text x="12" y="14" textAnchor="middle">?</text>
                      </g>
                    ) : null}
                  </g>
                ))}
              </g>
            )
          })}
          {layout.nodes.map((node) => (
            <g key={node.id} transform={`translate(${node.x} ${node.y})`} data-kind="state-node" data-focal={node.focal ? 'true' : undefined} aria-label={`${node.label}. Claude wrote this: ${node.detail}`}>
              <title>Claude wrote this: {node.detail}</title>
              <rect width={node.width} height={node.height} rx={node.entry ? 12 : 18} />
              <text x={node.width / 2} y={node.entry ? 28 : 30} textAnchor="middle">{node.label}</text>
              {node.detail ? <text x={node.width / 2} y="54" textAnchor="middle" data-kind="node-detail" textLength={Math.max(36, node.width - 26)} lengthAdjust="spacingAndGlyphs">{node.detail}</text> : null}
            </g>
          ))}
        </svg>
      )}
      <h3>Transitions</h3>
      <ul>{machine.transitions.map((transition) => <li key={transition.id}><button type="button" onClick={() => openTransition(transition)}>{transition.short}</button> · {transition.from} → {transition.to}{transition.blindSpot ? ` · Blind spot ${transition.blindSpot}` : ''}</li>)}</ul>
      {selectedTransition ? (
        <dialog open aria-label={`Transition ${selectedTransition.short}`}>
          <button type="button" onClick={() => setSelectedTransition(null)}>Close</button>
          <h3>{selectedTransition.short}</h3>
          <p><strong>Transition:</strong> {selectedTransition.from} → {selectedTransition.to}</p>
          <ClaudeCopy>{selectedTransition.event}</ClaudeCopy>
          <p><strong>Requirements:</strong> {selectedTransition.reqs.join(', ') || 'none'}</p>
          {selectedBlindSpotId ? <p><strong>Blind spot:</strong> {selectedBlindSpotId} <button type="button" onClick={() => openBlindSpot(selectedBlindSpotId)}>View details</button></p> : null}
        </dialog>
      ) : null}
      {selectedBlindSpot ? (
        <dialog open aria-label={`Blind spot ${selectedBlindSpot.id}`}>
          <button type="button" onClick={() => setSelectedBlindSpot(null)}>Close</button>
          <p><strong>{selectedBlindSpot.id}</strong></p>
          <h3>{selectedBlindSpot.title}</h3>
          <ClaudeCopy>{selectedBlindSpot.detail}</ClaudeCopy>
          <p><strong>Sources:</strong> {selectedBlindSpot.sources.join(', ') || 'none'}</p>
          {selectedBlindSpot.resolvedBy ? <p><strong>Resolved by:</strong> {selectedBlindSpot.resolvedBy}</p> : null}
          {selectedBlindSpot.acceptance ? <p><strong>Prior acceptance:</strong> {selectedBlindSpot.acceptance}</p> : null}
        </dialog>
      ) : null}
    </section>
  )
}

function SignOffView({ payload, spec, state, update, gates, createExport, onExport, importStatus, onImport }: {
  payload: LogicSpecPayload
  spec: LogicSpec
  state: ReviewState
  update: Update
  gates: ReviewGate[]
  createExport: () => Export
  onExport: (data: Export) => void
  importStatus: string | null
  onImport: (file: File) => void
}) {
  const allPassed = gates.every((gate) => gate.done >= gate.total)
  const record = decisionRecord(state, spec)
  const [copyStatus, setCopyStatus] = useState('')
  const download = () => {
    const data = createExport()
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${payload.slug}-decisions-${localStamp(new Date())}.json`
    anchor.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 0)
    onExport(data)
    setCopyStatus('Decision export downloaded.')
  }
  const copy = async () => {
    const data = createExport()
    try {
      if (!navigator.clipboard?.writeText) throw new Error('Clipboard unavailable')
      await navigator.clipboard.writeText(JSON.stringify(data, null, 2))
      onExport(data)
      setCopyStatus('Decision export copied.')
    } catch {
      setCopyStatus('Copy is blocked here — use Download')
    }
  }
  return (
    <section>
      <h2>Sign-off</h2>
      <p>Signing is the approval gate. All six gates must pass, and the verdict must be approve. Any later edit clears the signature.</p>
      <ol>{gates.map((gate) => <li key={gate.id} data-complete={gate.done >= gate.total}><strong>{gate.done >= gate.total ? '✓' : '○'} {gate.label}</strong> — {gate.done} / {gate.total}</li>)}</ol>
      <fieldset><legend>Your verdict</legend><label><input type="radio" name="verdict" checked={state.verdict === 'approve'} onChange={() => update((current) => ({ ...current, verdict: 'approve' }))} /> Approve</label><label><input type="radio" name="verdict" checked={state.verdict === 'send-back'} onChange={() => update((current) => ({ ...current, verdict: 'send-back' }))} /> Send back</label></fieldset>
      <label>Verdict note<textarea rows={3} value={state.verdictNote} onChange={(event) => update((current) => ({ ...current, verdictNote: event.target.value }))} /></label>
      {state.signedAt ? <p role="status" data-kind="signed">Signed {new Date(state.signedAt).toLocaleString()} · render {payload.renderId}</p> : null}
      <button type="button" disabled={!allPassed || state.verdict !== 'approve' || Boolean(state.signedAt)} onClick={() => update((current) => ({ ...current, signedAt: new Date().toISOString() }))}>{state.signedAt ? 'Signed' : 'Sign approval'}</button>
      {!allPassed ? <p>Signing is disabled until every gate is complete.</p> : state.verdict !== 'approve' ? <p>Choose approve to enable signing.</p> : null}
      <section><h3>Decision record</h3><pre>{JSON.stringify(record, null, 2)}</pre><div data-kind="export-actions"><button type="button" onClick={download}>Download decisions</button><button type="button" onClick={() => void copy()}>Copy decisions</button><label>Import decisions<input type="file" accept="application/json,.json" onChange={(event) => { const file = event.currentTarget.files?.[0]; if (file) onImport(file); event.currentTarget.value = '' }} /></label></div>{copyStatus ? <p role="status">{copyStatus}</p> : null}{importStatus ? <p role="status">{importStatus}</p> : null}</section>
    </section>
  )
}

function App() {
  const [payloadResult] = useState(readPayload)
  const payload = payloadResult.payload
  const [initial] = useState(() => payload ? bootstrap(payload) : null)
  const [state, setState] = useState<ReviewState>(() => initial?.state ?? emptyState())
  const stateRef = useRef(state)
  stateRef.current = state
  const [seen, setSeen] = useState<Record<string, string>>(() => initial?.seen ?? {})
  const seenRef = useRef(seen)
  seenRef.current = seen
  const [lastExportUpdatedAt, setLastExportUpdatedAt] = useState<string | null>(() => initial?.lastExportUpdatedAt ?? null)
  const lastExportRef = useRef(lastExportUpdatedAt)
  lastExportRef.current = lastExportUpdatedAt
  const [storageOk, setStorageOk] = useState(initial?.storageOk ?? true)
  const [view, setView] = useState<ViewId>('board')
  const [importStatus, setImportStatus] = useState<string | null>(null)
  const mode = useViewerMode()

  const persist = useCallback((next: ReviewState, currentSeen: Record<string, string>, exportedAt: string | null) => {
    if (!payload) return
    try {
      localStorage.setItem(`quirk-logic-spec:${payload.slug}`, JSON.stringify({ state: next, seen: currentSeen, lastExportUpdatedAt: exportedAt, renderId: payload.renderId }))
    } catch {
      setStorageOk(false)
    }
  }, [payload])

  const update = useCallback<Update>((recipe, reviewedItemId) => {
    const current = stateRef.current
    let next = recipe(current)
    if (current.signedAt && next !== current) next = { ...next, signedAt: undefined }
    next = { ...next, updatedAt: nextTimestamp(current.updatedAt) }
    let currentSeen = seenRef.current
    const reviewedHash = reviewedItemId && payload ? payload.itemHashes[reviewedItemId] : undefined
    if (reviewedItemId && reviewedHash !== undefined) {
      currentSeen = { ...currentSeen, [reviewedItemId]: reviewedHash }
      seenRef.current = currentSeen
      setSeen(currentSeen)
    }
    stateRef.current = next
    setState(next)
    persist(next, currentSeen, lastExportRef.current)
  }, [payload, persist])


  const changedIds = useMemo(() => new Set(payload ? changedItemIds(payload.spec, payload.itemHashes, seen) : []), [payload, seen])
  const gates = useMemo(() => payload ? gateList(state, payload.spec) : [], [payload, state])
  const gaps = useMemo(() => payload ? coverageGaps(payload.spec, state) : [], [payload, state])
  const tabs: TabSpec[] = useMemo(() => {
    if (!payload) return []
    const result: TabSpec[] = [
      { id: 'board', label: 'Scope board' },
      { id: 'risks', label: 'Risks' },
      { id: 'scenarios', label: 'Scenarios' },
    ]
    if (gaps.length > 0) result.push({ id: 'coverage', label: 'Coverage' })
    if (payload.spec.requirements.some((item) => item.certainty !== null)) result.push({ id: 'heatmap', label: 'Impact × certainty' })
    if (payload.spec.views?.storyMap) result.push({ id: 'story-map', label: 'Story map' })
    if (payload.spec.views?.stateMachine) result.push({ id: 'states', label: 'State machine' })
    result.push({ id: 'spec', label: 'Spec text' }, { id: 'sign-off', label: 'Sign-off' })
    return result
  }, [payload, gaps.length])

  useEffect(() => {
    if (payload && initial) persist(initial.state, initial.seen, initial.lastExportUpdatedAt)
  }, [initial, payload, persist])

  useEffect(() => {
    if (!tabs.some((tab) => tab.id === view)) setView('board')
  }, [tabs, view])

  useEffect(() => {
    const beforeUnload = (event: BeforeUnloadEvent) => {
      if (!storageOk && (!lastExportUpdatedAt || lastExportUpdatedAt !== state.updatedAt)) {
        event.preventDefault()
        event.returnValue = ''
      }
    }
    window.addEventListener('beforeunload', beforeUnload)
    return () => window.removeEventListener('beforeunload', beforeUnload)
  }, [lastExportUpdatedAt, state.updatedAt, storageOk])

  const createExport = useCallback((): Export => {
    if (!payload) throw new Error('No rendered review data is loaded.')
    return {
      kind: EXPORT_KIND,
      schemaVersion: 1,
      slug: payload.slug,
      renderId: payload.renderId,
      exportedAt: new Date().toISOString(),
      signed: Boolean(stateRef.current.signedAt),
      seen: { ...payload.itemHashes },
      state: cloneState(stateRef.current),
      record: decisionRecord(stateRef.current, payload.spec),
    }
  }, [payload])

  const onExport = useCallback((data: Export) => {
    const nextSeen = { ...data.seen }
    seenRef.current = nextSeen
    lastExportRef.current = data.state.updatedAt
    setSeen(nextSeen)
    setLastExportUpdatedAt(data.state.updatedAt)
    persist(stateRef.current, nextSeen, data.state.updatedAt)
  }, [persist])

  const importFile = useCallback((file: File) => {
    if (!payload) return
    void file.text().then((text) => {
      let parsed: unknown
      try { parsed = JSON.parse(text) } catch { setImportStatus('Import failed: file is not valid JSON.'); return }
      if (!isDecisionExport(parsed, payload.slug)) {
        setImportStatus('Import failed: expected a quirk logic spec decisions export for this spec slug.')
        return
      }
      const carried = carryOver(parsed.state, parsed.seen, payload.spec, payload.itemHashes, parsed.renderId, payload.renderId)
      stateRef.current = carried.state
      seenRef.current = carried.seen
      lastExportRef.current = parsed.state.updatedAt
      setState(carried.state)
      setSeen(carried.seen)
      setLastExportUpdatedAt(parsed.state.updatedAt)
      const signatureCleared = Boolean(parsed.state.signedAt && !carried.state.signedAt)
      setImportStatus(carried.changedIds.length
        ? `Imported. ${carried.changedIds.length} changed or new item${carried.changedIds.length === 1 ? '' : 's'} returned to review.`
        : signatureCleared ? 'Imported. The prior signature was cleared because the logic spec changed.' : 'Decision export imported.')
      persist(carried.state, carried.seen, parsed.state.updatedAt)
    }).catch(() => setImportStatus('Import failed: could not read the selected file.'))
  }, [payload, persist])

  const activeSpots = payload ? activeBlindSpots(state, payload.spec) : []
  const openGateCount = gates.filter((gate) => gate.done < gate.total).length
  const storageWarning = !storageOk

  if (payloadResult.error) return <Theme theme={neutralTheme} mode={mode}><main><h1>Review data error</h1><p role="alert">{payloadResult.error}</p></main></Theme>
  if (!payload) return <Theme theme={neutralTheme} mode={mode}><main><section><h1>Interactive logic spec review</h1><p>Open a rendered review.html to review a spec. This page is the unfilled template.</p></section></main></Theme>

  return (
    <Theme theme={neutralTheme} mode={mode}>
      <main>
        <header>
          <p data-kind="eyebrow">Interactive logic spec review · {payload.slug}</p>
          <h1>{payload.spec.title}</h1>
          <p>{state.signedAt ? `Signed ${new Date(state.signedAt).toLocaleString()}` : openGateCount === 0 ? 'Every gate is met. Record your verdict on Sign-off.' : `${openGateCount} of ${gates.length} review gates still open`}</p>
          <p role="status" data-kind={storageOk ? 'saved' : 'storage-warning'}>{storageOk ? 'Progress saved in this browser when available.' : 'Browser storage is unavailable. Export decisions before closing this page.'}</p>
          {storageWarning ? <aside role="alert"><strong>Export before closing.</strong> Storage failed; your progress may not survive this browser session.</aside> : null}
          <nav role="tablist" aria-label="Review views">{tabs.map((tab) => <button key={tab.id} type="button" role="tab" aria-selected={view === tab.id} aria-controls="review-panel" onClick={() => setView(tab.id)}>{tab.label}{tab.id === 'coverage' ? ` (${gaps.length})` : ''}</button>)}</nav>
        </header>
        <div id="review-panel" role="tabpanel" tabIndex={0}>
          {view === 'board' ? <ScopeBoard spec={payload.spec} state={state} update={update} changedIds={changedIds} /> : null}
          {view === 'risks' ? <RiskViews spec={payload.spec} state={state} update={update} changedIds={changedIds} /> : null}
          {view === 'scenarios' ? <ScenarioViews spec={payload.spec} state={state} update={update} changedIds={changedIds} /> : null}
          {view === 'coverage' ? <CoverageView spec={payload.spec} state={state} onNavigate={setView} /> : null}
          {view === 'heatmap' ? <ImpactCertaintyView spec={payload.spec} state={state} /> : null}
          {view === 'story-map' ? <StoryMapView spec={payload.spec} state={state} /> : null}
          {view === 'states' && payload.spec.views?.stateMachine ? <StateMachineView machine={payload.spec.views.stateMachine} blindSpots={payload.spec.blindSpots} /> : null}
          {view === 'spec' ? <section><h2>Spec text</h2><article><Markdown components={OFFLINE_MARKDOWN_COMPONENTS} contentWidth="100%">{payload.logicMarkdown}</Markdown></article></section> : null}
          {view === 'sign-off' ? <SignOffView payload={payload} spec={payload.spec} state={state} update={update} gates={gates} createExport={createExport} onExport={onExport} importStatus={importStatus} onImport={importFile} /> : null}
        </div>
        {storageWarning ? <aside role="alert" data-kind="persistent-warning"><strong>Storage unavailable:</strong> download or copy your decisions before closing this tab.</aside> : null}
        <footer><p>Local review only. No network connection is used. Render ID: <code>{payload.renderId}</code></p>{activeSpots.length ? <p>{activeSpots.length} active blind spot{activeSpots.length === 1 ? '' : 's'} require your attention.</p> : null}</footer>
      </main>
    </Theme>
  )
}

export default App
