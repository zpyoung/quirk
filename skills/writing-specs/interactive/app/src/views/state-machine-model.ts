import { useEffect, useState } from 'react'
import { effectivePlacement, GROUP_LABEL, GROUPS } from '../review-state'
import { layoutStateMachine, type MachineLayout } from '../layout'
import type { LogicSpec, ReviewState, StateMachine, StateMachineTransition } from '../spec-types'

export type StateMachineSelection = { kind: 'transition' | 'blind-spot'; id: string }

/** A homomorphic copy of an interface's shape, plain enough to satisfy Table's `Record<string, unknown>` row constraint. */
export type TableRow<T> = { [K in keyof T]: T[K] }

/** A lookup from every state or entry id in the machine to its display label. */
export function nodeLabels(machine: StateMachine): Map<string, string> {
  return new Map([
    ...machine.states.map((state) => [state.id, state.label] as const),
    ...(machine.entries ?? []).map((entry) => [entry.id, entry.label] as const),
  ])
}

/** The ids of states the machine marks as focal, for accenting the transitions that touch them. */
export function focalStateIds(machine: StateMachine): Set<string> {
  return new Set(machine.states.filter((state) => state.focal).map((state) => state.id))
}

/** A transition is out of scope once any requirement gating it has been placed out of scope. */
export function transitionOutOfScope(spec: LogicSpec, state: ReviewState, transition: StateMachineTransition): boolean {
  return transition.reqs.some((id) => {
    const requirement = spec.requirements.find((item) => item.id === id)
    return requirement !== undefined && effectivePlacement(state, requirement) === 'out'
  })
}

/** Token color for a transition's "Built?" column and diagram styling. */
export function builtColor(spec: LogicSpec, state: ReviewState, transition: StateMachineTransition): 'gray' | 'orange' | 'green' {
  if (transition.reqs.length === 0) return 'gray'
  return transitionOutOfScope(spec, state, transition) ? 'orange' : 'green'
}

/** What the "Built?" column shows for a transition's backing requirements. */
export function builtLabel(spec: LogicSpec, state: ReviewState, transition: StateMachineTransition): string {
  if (transition.reqs.length === 0) return 'Existing behavior'
  if (transitionOutOfScope(spec, state, transition)) return 'Not built — out of scope'
  const groups = new Set(transition.reqs.flatMap((id) => {
    const requirement = spec.requirements.find((item) => item.id === id)
    return requirement ? [requirement.group] : []
  }))
  return GROUPS.filter((group) => groups.has(group)).map((group) => GROUP_LABEL[group]).join(' + ')
}

/** The transition, if any, whose blind-spot chip points at this blind spot. */
export function transitionForBlindSpot(machine: StateMachine, blindSpotId: string): StateMachineTransition | undefined {
  return machine.transitions.find((transition) => transition.blindSpot === blindSpotId)
}

/** Computes the ELK layout for a state machine, recomputing whenever the machine itself changes. */
export function useMachineLayout(machine: StateMachine): { layout: MachineLayout | null; error: boolean } {
  const [layout, setLayout] = useState<MachineLayout | null>(null)
  const [error, setError] = useState(false)
  useEffect(() => {
    let alive = true
    setLayout(null)
    setError(false)
    void layoutStateMachine(machine).then((result) => { if (alive) setLayout(result) }).catch(() => { if (alive) { setLayout(null); setError(true) } })
    return () => { alive = false }
  }, [machine])
  return { layout, error }
}
