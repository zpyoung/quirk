import {
  useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState,
  type CSSProperties, type JSX, type KeyboardEvent as ReactKeyboardEvent, type PointerEvent as ReactPointerEvent, type ReactNode,
} from 'react'
import { flowAssets, loadAssets } from '../libs'
import {
  clampZoom, elkLayoutRun, fitView, isZoomedAway, layoutRun, panelHeight, placeCardForView, runStructureKey, viewBoxOf, wheelIntent, zoomFloor,
  type ElkConstructor, type GraphLayout, type Size, type View,
} from './layout'
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
  /** Starts the view here instead of at fit, so the zoomed-away state can be rendered directly. */
  initialView?: View
}

const FOCUS_ZOOM = 1
const FOCUS_MS = 400
const DEFAULT_SIZE: Size = { w: 960, h: 520 }
const DEFAULT_CARD_H = 280
const HINT_MS = 1500
const HINT_TEXT = 'Use ⌘ or Ctrl + scroll to zoom'

// the hint explains the wheel once per page load, however many graphs mount
let hintShown = false

// laid-out graphs by structure key, so a remounted graph starts from the ELK layout instead of the fallback
const elkCache = new Map<string, GraphLayout>()
const ELK_CACHE_MAX = 8

const reducedMotion = () => typeof window !== 'undefined' && !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

function summary(run: RunView): string {
  const tally = new Map<string, number>()
  for (const task of run.tasks) tally.set(task.status, (tally.get(task.status) ?? 0) + 1)
  const parts = [...tally].map(([status, n]) => `${n} ${status === 'needs-you' ? 'needs you' : status}`)
  const total = run.tasks.length
  return `Task dependency graph: ${total} ${total === 1 ? 'task' : 'tasks'}${parts.length ? `, ${parts.join(', ')}` : ''}`
}

/**
 * The run as a dependency graph: pan and zoom through the viewBox, a card beside the asking task. It paints the
 * synchronous fallback layout first and swaps in the ELK layout once the `flow` library has loaded; a failure
 * keeps the fallback.
 */
export function RunGraph({ run, serverNow, selected, focus, cardTask, card, stale, onSelect, initialView }: RunGraphProps): JSX.Element {
  const key = useMemo(() => runStructureKey(run), [run])
  const runRef = useRef(run)
  runRef.current = run
  // the structure key stands in for run: a status tick must not lay the graph out again
  const fallback = useMemo(() => layoutRun(runRef.current), [key])
  const [, setElkReady] = useState(0)
  const layout = elkCache.get(key) ?? fallback
  const [size, setSize] = useState<Size>(DEFAULT_SIZE)
  const [view, setViewState] = useState<View>(() => initialView ?? fitView(layout, DEFAULT_SIZE))
  const [tip, setTip] = useState<string | null>(null)
  const [hover, setHover] = useState<string | null>(null)
  const [dragging, setDragging] = useState(false)
  const [hint, setHint] = useState(false)
  const [panelH, setPanelH] = useState<number | null>(null)

  const rootRef = useRef<HTMLDivElement>(null)
  const svgRef = useRef<SVGSVGElement>(null)
  const viewRef = useRef(view)
  const sizeRef = useRef(size)
  const autoFit = useRef(initialView === undefined)
  const frame = useRef(0)
  const moved = useRef(false)
  const lastNonce = useRef<number | null>(null)
  const layoutRef = useRef(layout)
  const cardRef = useRef<HTMLDivElement>(null)
  const [cardH, setCardH] = useState(DEFAULT_CARD_H)
  sizeRef.current = size
  layoutRef.current = layout

  const setView = useCallback((next: View) => {
    viewRef.current = next
    setViewState(next)
  }, [])
  const stopAnimation = useCallback(() => {
    if (frame.current) cancelAnimationFrame(frame.current)
    frame.current = 0
  }, [])

  useLayoutEffect(() => {
    const root = rootRef.current
    if (!root) return
    const measure = () => {
      const next = panelHeight(window.innerHeight, root.getBoundingClientRect().top + window.scrollY)
      setPanelH((prev) => (prev === next ? prev : next))
    }
    measure()
    window.addEventListener('resize', measure)
    // the banner and status lines above the panel change its top edge without a window resize
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(measure)
    observer?.observe(root.closest('.run-view') ?? document.body)
    return () => {
      window.removeEventListener('resize', measure)
      observer?.disconnect()
    }
  }, [])

  useEffect(() => {
    if (!hint) return
    const timer = setTimeout(() => setHint(false), HINT_MS)
    return () => clearTimeout(timer)
  }, [hint])

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
    if (elkCache.has(key)) return
    let cancelled = false
    const compute = async () => {
      const win = window as unknown as { quirkFlow?: { ELK?: ElkConstructor } }
      if (!win.quirkFlow?.ELK) await loadAssets(flowAssets())
      const ELK = win.quirkFlow?.ELK
      if (!ELK) return
      const next = await elkLayoutRun(runRef.current, ELK)
      if (elkCache.size >= ELK_CACHE_MAX) elkCache.delete(elkCache.keys().next().value as string)
      elkCache.set(key, next)
      if (!cancelled) setElkReady((n) => n + 1)
    }
    compute().catch(() => {})
    return () => {
      cancelled = true
    }
  }, [key])

  useEffect(() => {
    if (autoFit.current) setView(fitView(layout, size))
  }, [layout, size, setView])

  const zoomAround = useCallback(
    (factor: number, px: number, py: number) => {
      const current = viewRef.current
      const sz = sizeRef.current
      const box = viewBoxOf(current, sz)
      const z = clampZoom(current.z * factor, zoomFloor(layoutRef.current, sz))
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
      if (wheelIntent(event) === 'scroll') {
        if (!hintShown) {
          hintShown = true
          setHint(true)
        }
        return
      }
      event.preventDefault()
      stopAnimation()
      autoFit.current = false
      // pinch gestures arrive as small deltas, so they get a steeper curve than a mouse wheel notch
      const dy = event.deltaMode === 1 ? event.deltaY * 33 : event.deltaY
      const rect = el.getBoundingClientRect()
      zoomAround(Math.exp(-dy * (Math.abs(dy) < 40 ? 0.01 : 0.0015)), event.clientX - rect.left, event.clientY - rect.top)
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

  const onKeyDown = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    if (event.ctrlKey || event.metaKey || event.altKey) return
    // the question card lives in this container and its text box must keep + and -
    if ((event.target as Element).closest?.('.run-graph-card')) return
    if (event.key === '+' || event.key === '=') zoomBy(1.25)
    else if (event.key === '-' || event.key === '_') zoomBy(0.8)
    else return
    event.preventDefault()
  }

  const select = useCallback(
    (id: string) => {
      if (moved.current) return
      onSelect(id)
    },
    [onSelect],
  )

  const tasks = useMemo(() => new Map(run.tasks.map((t) => [t.id, t])), [run])
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
            onTip={setTip}
          />
        )
      }),
    [layout, tasks, serverNow, selected, select],
  )

  const vb = viewBoxOf(view, size)
  const away = !autoFit.current && isZoomedAway(view, layout, size)
  const hot = hover ?? selected
  const tipTask = tip ? tasks.get(tip) : undefined
  const tipBox = tip ? layout.nodes.find((n) => n.id === tip) : undefined
  const cardBox = cardTask ? layout.nodes.find((n) => n.id === cardTask) : undefined

  const placement = cardBox ? placeCardForView(view, size, cardBox, cardH) : null
  const docked = placement?.mode === 'dock'

  useEffect(() => {
    const height = cardRef.current?.getBoundingClientRect().height
    if (height && Math.abs(height - cardH) > 1) setCardH(height)
  })

  return (
    <div
      ref={rootRef}
      className="run-graph-root"
      data-run-part="graph"
      style={panelH === null ? undefined : ({ '--run-graph-h': `${panelH}px` } as CSSProperties)}
      onKeyDown={onKeyDown}
    >
      <div className="run-graph-tools" role="group" aria-label="Graph view">
        {away ? (
          <button type="button" className="run-graph-show-all" onClick={fit}>
            Show all
          </button>
        ) : null}
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
                className="run-edge"
                d={edge.d}
                data-kind={edge.kind}
                data-from={edge.from}
                data-to={edge.to}
                data-failed={failed ? 'true' : undefined}
                data-flow={flowing ? 'true' : undefined}
                data-hot={hot === edge.from || hot === edge.to ? 'true' : undefined}
                markerEnd={failed ? 'url(#run-arrow-failed)' : 'url(#run-arrow)'}
              />
            )
          })}
        </g>
        <g className="run-nodes">{nodeLayer}</g>
        {tipTask?.mismatch && tipBox ? <MismatchTip text={tipTask.mismatch.text} x={tipBox.x} y={tipBox.y} /> : null}
      </svg>
      {hint ? (
        <div className="run-graph-hint" role="status">
          {HINT_TEXT}
        </div>
      ) : null}
      {placement ? (
        <div
          ref={cardRef}
          className="run-graph-card"
          data-dock={docked ? 'true' : undefined}
          style={placement.mode === 'beside' ? { left: placement.left, top: placement.top } : undefined}
        >
          {card}
        </div>
      ) : null}
    </div>
  )
}

function MismatchTip({ text, x, y }: { text: string; x: number; y: number }): JSX.Element {
  const lines = mismatchLines(text)
  const width = Math.max(...lines.map((l) => l.length)) * 7.6 + 24
  const height = lines.length * 19 + 16
  return (
    <g className="run-tip" transform={`translate(${x} ${y - height - 8})`} pointerEvents="none" role="tooltip">
      <rect width={width} height={height} rx={6} />
      {lines.map((line, i) => (
        <text key={i} x={12} y={24 + i * 19}>
          {line}
        </text>
      ))}
    </g>
  )
}
