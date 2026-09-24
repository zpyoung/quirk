import type { LogicSpec, Placement, Requirement, ReviewState, ScopeCondition } from '../spec-types'
import type { Update } from '../review-state'

export const isClaudeItem = (requirement: Requirement) => requirement.provenance === 'claude'

/** True while a Claude-authored requirement still has no reviewer call; nothing is preselected for it. */
export const isAwaitingCall = (state: ReviewState, requirement: Requirement) => isClaudeItem(requirement) && !state.placements[requirement.id]

export const CONDITIONS: ScopeCondition[] = ['no-code', 'under-10', 'under-30']

export function findRequirement(spec: LogicSpec, id: string): Requirement | undefined {
  return spec.requirements.find((requirement) => requirement.id === id)
}

/**
 * Applies a placement change: a Claude-authored item always records the reviewer's call, while
 * any other item stores an override only once it diverges from the spec's own placement, and
 * drops back to the baseline otherwise. Moving to 'conditional' without a specific condition
 * keeps the current or spec-proposed one; passing one (from a drag or the condition picker)
 * sets it directly.
 */
export function setPlacement(update: Update, requirement: Requirement, baseline: Placement, value: Placement, condition?: ScopeCondition) {
  update((state) => {
    const placements = { ...state.placements }
    const conditions = { ...state.conditions }
    if (isClaudeItem(requirement) || value !== baseline) placements[requirement.id] = value
    else delete placements[requirement.id]
    if (value === 'conditional') conditions[requirement.id] = condition ?? state.conditions[requirement.id] ?? requirement.condition ?? 'under-10'
    else delete conditions[requirement.id]
    return { ...state, placements, conditions }
  }, requirement.id)
}
