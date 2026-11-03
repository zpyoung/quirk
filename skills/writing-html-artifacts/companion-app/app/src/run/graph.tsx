import { useCallback, useEffect, useMemo, useRef, useState, type JSX, type PointerEvent as ReactPointerEvent, type ReactNode } from 'react'
import { layoutRun, type GraphLayout } from './layout'
import { mismatchLines, TaskNode } from './node'
import type { RunView } from './types'

export interface RunGraphProps {
  run: RunView
  serverNow: number
  selected: string | null
  focus: { task: string; nonce: number } | null
  cardTask: string | null
  card: ReactNode
  stale: boolean
  onSelect(task: string): void
}

interface View {
  cx: number
  cy: number
  z: number
}
interface Size {
  w: number
  h: number
}

const MIN_ZOOM = 0.2
const MAX_ZOOM = 3
const FOCUS_ZOOM = 1
const FOCUS_MS = 400
const DEFAULT_SIZE: Size = { w: 960, h: 520 }

const clampZoom = (z: number) => Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, z))
const reducedMotion = () => typeof window !== 'undefined' && !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

function fitView(layout: GraphLayout, size: Size): View {
  const z = clampZoom(Math.min(size.w / layout.width, size.h / layout.height, 1.25))
  return { cx: layout.width / 2, cy: layout.height / 2, z }
}

function viewBoxOf(view: View, size: Size) {
  const w = size.w / view.z
  const h = size.h / view.z
  return { x: view.cx - w / 2, y: view.cy - h / 2, w, h }
}

function summary(run: RunView): string {
  const tally = new Map<string, number>()
  for (const task of run.tasks) tally.set(task.status, (tally.get(task.status) ?? 0) + 1)
  const parts = [...tally].map(([status, n]) => `${n} ${status === 'needs-you' ? 'needs you' : status}`)
  const total = run.tasks.length
  return `Task dependency graph: ${total} ${total === 1 ? 'task' : 'tasks'}${parts.length ? `, ${parts.join(', ')}` : ''}`
}

/** The run as a dependency graph: columns by level, pan and zoom through the viewBox, a card beside the asking task. */
export function RunGraph({ run, serverNow, selected, focus, cardTask, card, stale, onSelect }: RunGraphProps): JSX.Element {
  const layout = useMemo(() => layoutRun(run), [run])
  const [size, setSize] = useState<Size>(DEFAULT_SIZE)
  const [view, setViewState] = useState<View>(() => fitView(layout, DEFAULT_SIZE))
  const [tip, setTip] = useState<string | null>(null)
  const [hover, setHover] = useState<string | null>(null)
  const [dragging, setDragging] = useState(false)

  const svgRef = useRef<SVGSVGElement>(null)
  const viewRef = useRef(view)
  const sizeRef = useRef(size)
  const autoFit = useRef(true)
  const frame = useRef(0)
  const moved = useRef(false)
  const lastNonce = useRef<number | null>(null)
  sizeRef.current = size

  const setView = useCallback((next: View) => {
    viewRef.current = next
    setViewState(next)
  }, [])
  const stopAnimation = useCallback(() => {
    if (frame.current) cancelAnimationFrame(frame.current)
    frame.current = 0
  }, [])

  useEffect(() => {
    const el = svgRef.current
    if (!el || typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect
      if (width > 0 && height > 0) setSize({ w: width, h: height })
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    if (autoFit.current) setView(fitView(layout, size))
  }, [layout.width, layout.height, size, setView])

  const zoomAround = useCallback(
    (factor: number, px: number, py: number) => {
      const current = viewRef.current
      const sz = sizeRef.current
      const box = viewBoxOf(current, sz)
      const z = clampZoom(current.z * factor)
      const wx = box.x + px / current.z
      const wy = box.y + py / current.z
      setView({ cx: wx - px / z + sz.w / (2 * z), cy: wy - py / z + sz.h / (2 * z), z })
    },
    [setView],
  )

  useEffect(() => {
    const el = svgRef.current
    if (!el) return
    const onWheel = (event: WheelEvent) => {
      event.preventDefault()
      stopAnimation()
      autoFit.current = false
      const rect = el.getBoundingClientRect()
      zoomAround(Math.exp(-event.deltaY * 0.0015), event.clientX - rect.left, event.clientY - rect.top)
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [zoomAround, stopAnimation])

  const animateTo = useCallback(
    (target: View) => {
      stopAnimation()
      const from = viewRef.current
      if (reducedMotion()) {
        setView(target)
        return
      }
      const start = performance.now()
      const step = (now: number) => {
        const t = Math.min(1, (now - start) / FOCUS_MS)
        const e = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2
        setView({
          cx: from.cx + (target.cx - from.cx) * e,
          cy: from.cy + (target.cy - from.cy) * e,
          z: from.z * Math.pow(target.z / from.z, e),
        })
        frame.current = t < 1 ? requestAnimationFrame(step) : 0
      }
      frame.current = requestAnimationFrame(step)
    },
    [setView, stopAnimation],
  )

  useEffect(() => {
    if (!focus || focus.nonce === lastNonce.current) return
    const node = layout.nodes.find((n) => n.id === focus.task)
    if (!node) return
    lastNonce.current = focus.nonce
    autoFit.current = false
    animateTo({ cx: node.x + node.w / 2, cy: node.y + node.h / 2, z: Math.max(FOCUS_ZOOM, viewRef.current.z) })
  }, [focus?.nonce, focus?.task, layout, animateTo])

  useEffect(() => stopAnimation, [stopAnimation])

  const drag = useRef<{ x: number; y: number; cx: number; cy: number } | null>(null)
  const onPointerDown = (event: ReactPointerEvent<SVGSVGElement>) => {
    if (event.button !== 0) return
    stopAnimation()
    moved.current = false
    drag.current = { x: event.clientX, y: event.clientY, cx: viewRef.current.cx, cy: viewRef.current.cy }
    const move = (e: PointerEvent) => {
      const start = drag.current
      if (!start) return
      const dx = e.clientX - start.x
      const dy = e.clientY - start.y
      if (!moved.current && Math.hypot(dx, dy) < 4) return
      if (!moved.current) {
        moved.current = true
        autoFit.current = false
        setDragging(true)
      }
      const z = viewRef.current.z
      setView({ cx: start.cx - dx / z, cy: start.cy - dy / z, z })
    }
    const up = () => {
      drag.current = null
      setDragging(false)
      // the click that ends a drag fires before this timer, so only keyboard selects see moved cleared
      setTimeout(() => {
        moved.current = false
      }, 0)
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
      window.removeEventListener('pointercancel', up)
    }
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)
    window.addEventListener('pointercancel', up)
  }

  const fit = () => {
    autoFit.current = true
    animateTo(fitView(layout, sizeRef.current))
  }
  const zoomBy = (factor: number) => {
    stopAnimation()
    autoFit.current = false
    zoomAround(factor, sizeRef.current.w / 2, sizeRef.current.h / 2)
  }

  const select = useCallback(
    (id: string) => {
      if (moved.current) return
      onSelect(id)
    },
    [onSelect],
  )

  const tasks = useMemo(() => new Map(run.tasks.map((t) => [t.id, t])), [run])
  const joinedAbove = new Set<string>()
  const joinedBelow = new Set<string>()
  for (const edge of layout.edges) {
    if (!edge.joined) continue
    const a = layout.nodes.find((n) => n.id === edge.from)
    const b = layout.nodes.find((n) => n.id === edge.to)
    if (!a || !b) continue
    const [upper, lower] = a.y <= b.y ? [a, b] : [b, a]
    joinedBelow.add(upper.id)
    joinedAbove.add(lower.id)
  }

  const nodeLayer = useMemo(
    () =>
      layout.nodes.map((box) => {
        const task = tasks.get(box.id)
        if (!task) return null
        return (
          <TaskNode
            key={box.id}
            task={task}
            box={box}
            serverNow={serverNow}
            selected={selected === box.id}
            onSelect={select}
            joinedAbove={joinedAbove.has(box.id)}
            joinedBelow={joinedBelow.has(box.id)}
            onTip={setTip}
          />
        )
      }),
    // the joined sets derive from layout, so layout stands in for them
    [layout, tasks, serverNow, selected, select],
  )

  const vb = viewBoxOf(view, size)
  const hot = hover ?? selected
  const tipTask = tip ? tasks.get(tip) : undefined
  const tipBox = tip ? layout.nodes.find((n) => n.id === tip) : undefined
  const cardBox = cardTask ? layout.nodes.find((n) => n.id === cardTask) : undefined

  let cardStyle: { left?: number; right?: number; top: number } | null = null
  if (cardBox) {
    const rightPx = (cardBox.x + cardBox.w - vb.x) * view.z + 14
    const leftPx = (cardBox.x - vb.x) * view.z - 14
    const top = Math.max(0, Math.min((cardBox.y - vb.y) * view.z, size.h - 40))
    cardStyle = rightPx + 352 <= size.w || leftPx < 352 ? { left: Math.max(0, rightPx), top } : { right: Math.max(0, size.w - leftPx), top }
  }

  return (
    <div className="run-graph-root" data-run-part="graph">
      <div className="run-graph-tools" role="group" aria-label="Graph view">
        <button type="button" onClick={fit}>
          Fit
        </button>
        <button type="button" aria-label="Zoom in" onClick={() => zoomBy(1.25)}>
          +
        </button>
        <button type="button" aria-label="Zoom out" onClick={() => zoomBy(0.8)}>
          −
        </button>
      </div>
      <svg
        ref={svgRef}
        className="run-graph"
        role="img"
        aria-label={summary(run)}
        viewBox={`${vb.x.toFixed(2)} ${vb.y.toFixed(2)} ${vb.w.toFixed(2)} ${vb.h.toFixed(2)}`}
        data-stale={stale ? 'true' : undefined}
        data-dragging={dragging ? 'true' : undefined}
        data-hot={hot ?? undefined}
        onPointerDown={onPointerDown}
        onPointerOver={(event) => {
          const id = (event.target as Element).closest?.('.run-node')?.getAttribute('data-task') ?? null
          setHover((prev) => (prev === id ? prev : id))
        }}
        onPointerLeave={() => setHover(null)}
      >
        <defs>
          <marker id="run-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto">
            <path className="run-arrow" d="M0,1 L10,5 L0,9 Z" />
          </marker>
          <marker id="run-arrow-failed" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto">
            <path className="run-arrow run-arrow-failed" d="M0,1 L10,5 L0,9 Z" />
          </marker>
          <linearGradient id="run-shimmer-grad" x1="0" x2="1" y1="0" y2="0">
            <stop offset="0" stopColor="currentColor" stopOpacity="0" />
            <stop offset="0.5" stopColor="currentColor" stopOpacity="0.28" />
            <stop offset="1" stopColor="currentColor" stopOpacity="0" />
          </linearGradient>
        </defs>
        <g className="run-edges">
          {layout.edges.map((edge) => {
            const source = tasks.get(edge.from)
            const target = tasks.get(edge.to)
            const failed = source?.status === 'failed'
            const flowing = edge.kind === 'dep' && source?.status === 'passed' && (target?.status === 'running' || target?.status === 'retrying')
            return (
              <path
                key={`${edge.kind}:${edge.from}>${edge.to}`}
                className={edge.joined ? 'run-edge run-edge-join' : 'run-edge'}
                d={edge.d}
                data-kind={edge.kind}
                data-from={edge.from}
                data-to={edge.to}
                data-joined={edge.joined ? 'true' : undefined}
                data-failed={failed ? 'true' : undefined}
                data-flow={flowing ? 'true' : undefined}
                data-hot={hot === edge.from || hot === edge.to ? 'true' : undefined}
                markerEnd={edge.joined ? undefined : failed ? 'url(#run-arrow-failed)' : 'url(#run-arrow)'}
              />
            )
          })}
        </g>
        <g className="run-nodes">{nodeLayer}</g>
        {tipTask?.mismatch && tipBox ? <MismatchTip text={tipTask.mismatch.text} x={tipBox.x} y={tipBox.y} /> : null}
      </svg>
      {cardStyle ? (
        <div className="run-graph-card" style={cardStyle}>
          {card}
        </div>
      ) : null}
    </div>
  )
}

function MismatchTip({ text, x, y }: { text: string; x: number; y: number }): JSX.Element {
  const lines = mismatchLines(text)
  const width = Math.max(...lines.map((l) => l.length)) * 6.4 + 20
  const height = lines.length * 15 + 14
  return (
    <g className="run-tip" transform={`translate(${x} ${y - height - 8})`} pointerEvents="none" role="tooltip">
      <rect width={width} height={height} rx={6} />
      {lines.map((line, i) => (
        <text key={i} x={10} y={20 + i * 15}>
          {line}
        </text>
      ))}
    </g>
  )
}
