import ELK from 'elkjs/lib/elk.bundled.js'
import type { ElkNode } from 'elkjs'
import type { StateMachine } from './spec-types'

export interface MachineLayoutNode {
  id: string
  label: string
  detail: string
  focal: boolean
  entry: boolean
  x: number
  y: number
  width: number
  height: number
}

export interface MachineLayoutLabel {
  id: string
  x: number
  y: number
  width: number
  height: number
}

export interface MachineLayoutEdge {
  id: string
  sections: { path: string }[]
  labels: MachineLayoutLabel[]
}

export interface MachineLayout {
  width: number
  height: number
  nodes: MachineLayoutNode[]
  edges: MachineLayoutEdge[]
}

const elk = new ELK()
const CORNER = 8

function pointPath(section: { startPoint: { x: number; y: number }; bendPoints?: { x: number; y: number }[]; endPoint: { x: number; y: number } }): string {
  const points = [section.startPoint, ...(section.bendPoints ?? []), section.endPoint]
  const [first, ...rest] = points
  let path = `M ${first!.x} ${first!.y}`
  for (let index = 0; index < rest.length; index += 1) {
    const point = rest[index]!
    const next = rest[index + 1]
    if (!next) {
      path += ` L ${point.x} ${point.y}`
      break
    }
    const previous = index === 0 ? first! : rest[index - 1]!
    const inX = Math.sign(point.x - previous.x)
    const inY = Math.sign(point.y - previous.y)
    const outX = Math.sign(next.x - point.x)
    const outY = Math.sign(next.y - point.y)
    if ((inX === outX && inY === outY) || (inX === 0 && inY === 0) || (outX === 0 && outY === 0)) {
      path += ` L ${point.x} ${point.y}`
      continue
    }
    const radius = Math.min(CORNER, Math.hypot(point.x - previous.x, point.y - previous.y) / 2, Math.hypot(next.x - point.x, next.y - point.y) / 2)
    if (radius <= 0) {
      path += ` L ${point.x} ${point.y}`
      continue
    }
    const sweep = inX * outY - inY * outX > 0 ? 1 : 0
    path += ` L ${point.x - inX * radius} ${point.y - inY * radius} A ${radius} ${radius} 0 0 ${sweep} ${point.x + outX * radius} ${point.y + outY * radius}`
  }
  return path
}

export async function layoutStateMachine(machine: StateMachine): Promise<MachineLayout> {
  const entries = machine.entries ?? []
  const stateNodeIds = new Map(machine.states.map((state) => [state.id, `state:${state.id}`]))
  const entryNodeIds = new Map(entries.map((entry) => [entry.id, `entry:${entry.id}`]))
  const nodes: MachineLayoutNode[] = [
    ...entries.map((entry) => ({ id: `entry:${entry.id}`, label: entry.label, detail: '', focal: false, entry: true, x: 0, y: 0, width: Math.max(148, entry.label.length * 8 + 30), height: 48 })),
    ...machine.states.map((state) => ({ id: `state:${state.id}`, label: state.label, detail: state.detail, focal: Boolean(state.focal), entry: false, x: 0, y: 0, width: 242, height: 100 })),
  ]
  const byId = new Map(nodes.map((node) => [node.id, node]))
  const graph: ElkNode = {
    id: 'state-machine',
    layoutOptions: {
      'elk.algorithm': 'layered',
      'elk.direction': 'RIGHT',
      'elk.edgeRouting': 'ORTHOGONAL',
      'elk.spacing.nodeNode': '44',
      'elk.layered.spacing.nodeNodeBetweenLayers': '88',
      'elk.layered.spacing.edgeNodeBetweenLayers': '34',
      'elk.layered.spacing.edgeEdgeBetweenLayers': '24',
      'elk.edgeLabels.inline': 'true',
      'elk.layered.edgeLabels.inline': 'true',
      'elk.layered.nodePlacement.favorStraightEdges': 'true',
    },
    children: nodes.map((node) => ({ id: node.id, width: node.width, height: node.height })),
    edges: machine.transitions.flatMap((transition) => {
      const source = stateNodeIds.get(transition.from) ?? entryNodeIds.get(transition.from)
      const target = stateNodeIds.get(transition.to)
      if (!source || !target) return []
      const chipWidth = transition.blindSpot ? 34 : 0
      const labelWidth = Math.max(104, transition.short.length * 7.3 + chipWidth + 22)
      return [{
        id: transition.id,
        sources: [source],
        targets: [target],
        labels: [{ id: `label:${transition.id}`, text: transition.short, width: labelWidth, height: 28 }],
      }]
    }),
  }
  const result = await elk.layout(graph)
  const layoutNodes = (result.children ?? []).flatMap((position) => {
    const node = byId.get(position.id)
    if (!node) return []
    return [{ ...node, x: position.x ?? 0, y: position.y ?? 0, width: position.width ?? node.width, height: position.height ?? node.height }]
  })
  const edges: MachineLayoutEdge[] = (result.edges ?? []).map((edge) => ({
    id: edge.id,
    sections: (edge.sections ?? []).map((section) => ({ path: pointPath(section) })),
    labels: (edge.labels ?? []).map((label) => ({
      id: label.id ?? `label:${edge.id}`,
      x: label.x ?? 0,
      y: label.y ?? 0,
      width: label.width ?? 0,
      height: label.height ?? 0,
    })),
  }))
  return {
    width: result.width ?? 0,
    height: result.height ?? 0,
    nodes: layoutNodes,
    edges,
  }
}
