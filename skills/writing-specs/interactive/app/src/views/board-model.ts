import type { LogicSpec, Placement, Requirement, ScopeCondition } from '../spec-types'
import type { Update } from '../review-state'

export const CONDITIONS: ScopeCondition[] = ['no-code', 'under-10', 'under-30']

export function findRequirement(spec: LogicSpec, id: string): Requirement | undefined {
  return spec.requirements.find((requirement) => requirement.id === id)
}

/**
 * Applies a placement change: a requirement stores an override only once it diverges from
 * Claude's pre-filled placement, and drops back to the baseline otherwise. Moving to 'conditional'
 * without a specific condition keeps the current or spec-proposed one; passing one (from a drag or
 * the condition picker) sets it directly.
 */
export function setPlacement(update: Update, requirement: Requirement, baseline: Placement, value: Placement, condition?: ScopeCondition) {
  update((state) => {
    const placements = { ...state.placements }
    const conditions = { ...state.conditions }
    if (value !== baseline) placements[requirement.id] = value
    else delete placements[requirement.id]
    if (value === 'conditional') conditions[requirement.id] = condition ?? state.conditions[requirement.id] ?? requirement.condition ?? 'under-10'
    else delete conditions[requirement.id]
    return { ...state, placements, conditions }
  }, requirement.id)
}
