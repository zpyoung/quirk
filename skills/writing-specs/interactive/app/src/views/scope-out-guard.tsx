import { createContext, useContext, useState, type ReactNode } from 'react'
import { AlertDialog } from '@astryxdesign/core/AlertDialog'
import type { LogicSpec, Requirement, ReviewState } from '../spec-types'
import { effectivePlacement } from '../review-state'

type Dependent = { requirement: Requirement; via?: string }
type Pending = { requirement: Requirement; dependents: Dependent[]; apply: () => void }
type Guard = (spec: LogicSpec, state: ReviewState, requirement: Requirement, apply: () => void) => void

/** In-scope requirements that need `requirement`, directly or through a chain of other requirements. */
function inScopeDependents(spec: LogicSpec, state: ReviewState, requirement: Requirement): Dependent[] {
  const found = new Map<string, Dependent>()
  const queue: { id: string; via?: string }[] = [{ id: requirement.id }]
  while (queue.length > 0) {
    const { id, via } = queue.shift()!
    for (const candidate of spec.requirements) {
      if (candidate.id === requirement.id || found.has(candidate.id) || !candidate.dependsOn.includes(id)) continue
      const placement = effectivePlacement(state, candidate)
      if (placement === undefined || placement === 'out') continue
      const nextVia = id === requirement.id ? undefined : (via ?? id)
      found.set(candidate.id, { requirement: candidate, via: nextVia })
      queue.push({ id: candidate.id, via: id === requirement.id ? candidate.id : (via ?? id) })
    }
  }
  return [...found.values()]
}

const GuardContext = createContext<Guard>((_spec, _state, _requirement, apply) => apply())

/** Wraps the review so moving a requirement out of scope first confirms when in-scope requirements still depend on it. */
export function ScopeOutGuardProvider({ children }: { children: ReactNode }) {
  const [pending, setPending] = useState<Pending | null>(null)
  const guard: Guard = (spec, state, requirement, apply) => {
    const dependents = inScopeDependents(spec, state, requirement)
    if (dependents.length === 0) apply()
    else setPending({ requirement, dependents, apply })
  }
  const direct = pending?.dependents.filter((d) => !d.via) ?? []
  const indirect = pending?.dependents.filter((d) => d.via) ?? []
  const describe = () =>
    [
      `${direct.length} in-scope requirement${direct.length === 1 ? ' needs' : 's need'} it directly: ${direct.map((d) => `${d.requirement.id} (${d.requirement.summary.replace(/\.$/, '')})`).join('; ')}.`,
      indirect.length > 0 ? `${indirect.length} more depend on those: ${indirect.map((d) => d.requirement.id).join(', ')}.` : '',
      'They stay in scope but lose something they need, so the spec has a gap until you move them too or change them.',
    ]
      .filter(Boolean)
      .join(' ')
  return (
    <GuardContext.Provider value={guard}>
      {children}
      {pending ? (
        <AlertDialog
          isOpen
          width={600}
          onOpenChange={(open) => !open && setPending(null)}
          title={`Move ${pending.requirement.id} out of scope?`}
          description={describe()}
          cancelLabel="Keep it in scope"
          actionLabel="Move out anyway"
          onAction={() => {
            pending.apply()
            setPending(null)
          }}
        />
      ) : null}
    </GuardContext.Provider>
  )
}

export const useScopeOutGuard = () => useContext(GuardContext)
