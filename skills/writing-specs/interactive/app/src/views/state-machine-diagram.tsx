import { useState, type KeyboardEvent, type ReactNode } from 'react'
import { Card } from '@astryxdesign/core/Layout'
import { ScrollableArea } from '@astryxdesign/core/ScrollableArea'
import { activeBlindSpots } from '../review-state'
import { blindSpotChipWidth, type MachineLayout } from '../layout'
import type { LogicSpec, ReviewState, StateMachine } from '../spec-types'
import { focalStateIds, transitionOutOfScope, type StateMachineSelection } from './state-machine-model'

type Props = {
  machine: StateMachine
  spec: LogicSpec
  state: ReviewState
  layout: MachineLayout
  onSelect: (selection: StateMachineSelection) => void
}

export const MASK = 'var(--color-background-card)'
export const INK = 'var(--color-text-primary)'
export const MUTED = 'var(--color-text-secondary)'
export const OFF = 'var(--color-text-disabled)'
export const ACCENT = 'var(--color-text-orange)'

function wrapLines(text: string, maxChars: number, maxLines: number): string[] {
  const lines: string[] = []
  let current = ''
  for (const word of text.split(/\s+/).filter(Boolean)) {
    const candidate = current ? `${current} ${word}` : word
    if (candidate.length <= maxChars || !current) {
      current = candidate
      continue
    }
    lines.push(current)
    current = word
  }
  if (current) lines.push(current)
  if (lines.length <= maxLines) return lines
  const kept = lines.slice(0, maxLines)
  kept[maxLines - 1] = `${kept[maxLines - 1]!.replace(/[.,;:]?$/, '')}…`
  return kept
}

function ArrowMarker({ id, color }: { id: string; color: string }) {
  return (
    <marker id={id} markerWidth={8} markerHeight={6} refX={7} refY={3} orient="auto" markerUnits="userSpaceOnUse">
      <polygon points="0 0, 8 3, 0 6" fill={color} />
    </marker>
  )
}

function Clickable({ label, onActivate, onHover, children }: { label: string; onActivate: () => void; onHover: (isHovered: boolean) => void; children: ReactNode }) {
  const onKeyDown = (event: KeyboardEvent<SVGGElement>) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      onActivate()
    }
  }
  return (
    <g role="button" tabIndex={0} aria-label={label} cursor="pointer" onClick={onActivate} onKeyDown={onKeyDown} onMouseEnter={() => onHover(true)} onMouseLeave={() => onHover(false)} onFocus={() => onHover(true)} onBlur={() => onHover(false)}>
      {children}
    </g>
  )
}

function BlindSpotChip({ id, active, isHovered }: { id: string; active: boolean; isHovered: boolean }) {
  const width = blindSpotChipWidth(id)
  return (
    <g>
      <title>{`Blind spot ${id}${active ? '' : ' (cleared by your placement)'}`}</title>
      <rect width={width} height={18} rx={4} fill={active ? 'var(--color-error-muted)' : MASK} stroke={active ? 'var(--color-error)' : OFF} strokeWidth={isHovered ? 2 : 1} strokeDasharray={active ? undefined : '3,2'} />
      <text x={width / 2} y={13} textAnchor="middle" fontSize={9} fontWeight={600} fill={active ? 'var(--color-error)' : OFF}>
        {id}
      </text>
    </g>
  )
}

function EdgeLabel({ width, height, title, detail, color, chipWidth }: { width: number; height: number; title: string; detail: string; color: string; chipWidth: number }) {
  const centerX = (chipWidth ? width - chipWidth - 4 : width) / 2
  return (
    <g>
      <rect width={width} height={height} rx={4} fill={MASK} />
      <text x={centerX} y={detail ? height / 2 - 3 : height / 2 + 3} textAnchor="middle" fontSize={9} fontWeight={600} letterSpacing="0.05em" fill={color}>
        {title.toUpperCase()}
      </text>
      {detail ? (
        <text x={centerX} y={height / 2 + 11} textAnchor="middle" fontSize={8} fill={color === ACCENT ? ACCENT : MUTED}>
          {detail}
        </text>
      ) : null}
    </g>
  )
}

function StateBox({ width, height, label, detail, focal }: { width: number; height: number; label: string; detail: string; focal: boolean }) {
  return (
    <g>
      <title>{`Claude wrote this: ${detail}`}</title>
      <rect width={width} height={height} rx={8} fill={focal ? 'var(--color-background-orange)' : 'var(--color-background-surface)'} stroke={focal ? ACCENT : INK} strokeWidth={focal ? 1.5 : 1} />
      <text x={12} y={20} fontSize={8} fontWeight={600} letterSpacing="0.18em" fill={focal ? ACCENT : MUTED}>
        STATE
      </text>
      <text x={width / 2} y={46} textAnchor="middle" fontSize={15} fontWeight={600} fill={INK}>
        {label}
      </text>
      {wrapLines(detail, Math.floor((width - 24) / 5.4), 3).map((line, index) => (
        <text key={index} x={width / 2} y={64 + index * 12} textAnchor="middle" fontSize={10} fill={MUTED}>
          {line}
        </text>
      ))}
    </g>
  )
}

function EntryBox({ width, height, label }: { width: number; height: number; label: string }) {
  return (
    <g>
      <rect width={width} height={height} rx={6} fill="var(--color-background-muted)" stroke={OFF} strokeWidth={1} />
      <text x={12} y={18} fontSize={8} fontWeight={600} letterSpacing="0.18em" fill={MUTED}>
        ENTRY
      </text>
      <text x={12} y={36} fontSize={12} fontWeight={600} fill={INK}>
        {label}
      </text>
    </g>
  )
}

/** The spec's state machine, laid out by ELK: every drawn transition is a spec rule, dashed when its requirements are out of scope, with blind-spot chips where they apply. */
export function StateMachineDiagram({ machine, spec, state, layout, onSelect }: Props) {
  const [hovered, setHovered] = useState<string | null>(null)
  const hover = (id: string) => (isHovered: boolean) => setHovered((current) => (isHovered ? id : current === id ? null : current))
  const transitionById = new Map(machine.transitions.map((transition) => [transition.id, transition]))
  const focal = focalStateIds(machine)
  const active = new Set(activeBlindSpots(state, spec).map((spot) => spot.id))

  return (
    <Card padding={2}>
      <ScrollableArea axis="inline" label="State machine diagram">
        <svg width={layout.width} height={layout.height} viewBox={`0 0 ${layout.width} ${layout.height}`} role="group" aria-labelledby="state-machine-title state-machine-desc" fontFamily="inherit">
          <title id="state-machine-title">The spec's state machine</title>
          <desc id="state-machine-desc">
            States, entries, and the transitions between them, each labelled with the requirements behind it and any blind spot it carries. Every transition, state, and blind spot opens its details.
          </desc>
          <defs>
            <ArrowMarker id="sm-arrow" color={MUTED} />
            <ArrowMarker id="sm-arrow-accent" color={ACCENT} />
            <ArrowMarker id="sm-arrow-off" color={OFF} />
            <ArrowMarker id="sm-arrow-hover" color={INK} />
          </defs>

          {layout.edges.map((edge) => {
            const transition = transitionById.get(edge.id)
            if (!transition) return null
            const off = transitionOutOfScope(spec, state, transition)
            const isFocal = !off && (focal.has(transition.from) || focal.has(transition.to))
            const color = off ? OFF : isFocal ? ACCENT : MUTED
            const marker = off ? 'sm-arrow-off' : isFocal ? 'sm-arrow-accent' : 'sm-arrow'
            const isHovered = hovered === transition.id
            return (
              <Clickable key={edge.id} label={`Transition: ${transition.short}. Open details.`} onActivate={() => onSelect({ kind: 'transition', id: transition.id })} onHover={hover(transition.id)}>
                {edge.sections.map((section, index) => (
                  <g key={index}>
                    <path d={section.path} fill="none" stroke="transparent" strokeWidth={16} pointerEvents="stroke" />
                    <path d={section.path} fill="none" stroke={isHovered ? INK : color} strokeWidth={(isFocal ? 1.5 : 1.2) + (isHovered ? 1 : 0)} strokeDasharray={off ? '5,4' : undefined} markerEnd={`url(#${isHovered ? 'sm-arrow-hover' : marker})`} />
                  </g>
                ))}
              </Clickable>
            )
          })}

          {layout.edges.map((edge) => {
            const transition = transitionById.get(edge.id)
            const label = edge.labels[0]
            if (!transition || !label) return null
            const off = transitionOutOfScope(spec, state, transition)
            const isFocal = !off && (focal.has(transition.from) || focal.has(transition.to))
            const color = hovered === transition.id ? INK : off ? OFF : isFocal ? ACCENT : MUTED
            const detail = transition.reqs.join(' · ')
            return (
              <Clickable key={edge.id} label={`Transition: ${transition.short}. Open details.`} onActivate={() => onSelect({ kind: 'transition', id: transition.id })} onHover={hover(transition.id)}>
                <g transform={`translate(${label.x} ${label.y})`}>
                  <EdgeLabel width={label.width} height={label.height} title={transition.short} detail={detail} color={color} chipWidth={transition.blindSpot ? blindSpotChipWidth(transition.blindSpot) : 0} />
                </g>
              </Clickable>
            )
          })}

          {layout.edges.map((edge) => {
            const transition = transitionById.get(edge.id)
            const label = edge.labels[0]
            if (!transition?.blindSpot || !label) return null
            const blindSpotId = transition.blindSpot
            return (
              <Clickable key={`${edge.id}-chip`} label={`Blind spot ${blindSpotId}. Open details.`} onActivate={() => onSelect({ kind: 'blind-spot', id: blindSpotId })} onHover={hover(blindSpotId)}>
                <g transform={`translate(${label.x + label.width - blindSpotChipWidth(blindSpotId)} ${label.y + (label.height - 18) / 2})`}>
                  <BlindSpotChip id={blindSpotId} active={active.has(blindSpotId)} isHovered={hovered === blindSpotId} />
                </g>
              </Clickable>
            )
          })}

          {layout.nodes.map((node) => (
            <g key={node.id} transform={`translate(${node.x} ${node.y})`}>
              {node.entry ? <EntryBox width={node.width} height={node.height} label={node.label} /> : <StateBox width={node.width} height={node.height} label={node.label} detail={node.detail} focal={node.focal} />}
            </g>
          ))}
        </svg>
      </ScrollableArea>
    </Card>
  )
}
