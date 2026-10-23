import { useRef, useState, type KeyboardEvent, type PointerEvent } from "react"

import { cn } from "@/lib/utils"

import { clamp, formatClock } from "./playback"

const STEP_MS = 5000
const PAGE_MS = 30000

/** Time slider with a filled track, a floating time with milliseconds under the pointer, and the standard slider keys. */
export function SeekSlider({
  value,
  max,
  onChange,
  onSpace,
  label = "Seek",
  className,
}: {
  value: number
  max: number
  onChange: (ms: number) => void
  /** Called on Space; the keyboard layer ignores keys on a slider, so the slider forwards this one. */
  onSpace?: () => void
  label?: string
  className?: string
}) {
  const trackRef = useRef<HTMLDivElement>(null)
  const dragging = useRef(false)
  const [hover, setHover] = useState<number | null>(null)

  const timeAt = (clientX: number) => {
    const rect = trackRef.current?.getBoundingClientRect()
    if (!rect || rect.width === 0) return 0
    return clamp((clientX - rect.left) / rect.width, 0, 1) * max
  }

  const onPointerDown = (event: PointerEvent<HTMLDivElement>) => {
    if (event.button !== 0) return
    dragging.current = true
    event.currentTarget.setPointerCapture(event.pointerId)
    event.currentTarget.focus({ preventScroll: true })
    const at = timeAt(event.clientX)
    setHover(at)
    onChange(at)
  }

  const onPointerMove = (event: PointerEvent<HTMLDivElement>) => {
    const at = timeAt(event.clientX)
    setHover(at)
    if (dragging.current) onChange(at)
  }

  const onPointerUp = (event: PointerEvent<HTMLDivElement>) => {
    dragging.current = false
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId)
    }
  }

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === " " && onSpace) {
      event.preventDefault()
      event.stopPropagation()
      if (!event.repeat) onSpace()
      return
    }
    let next: number | null = null
    if (event.key === "ArrowRight" || event.key === "ArrowUp") next = value + STEP_MS
    else if (event.key === "ArrowLeft" || event.key === "ArrowDown") next = value - STEP_MS
    else if (event.key === "PageUp") next = value + PAGE_MS
    else if (event.key === "PageDown") next = value - PAGE_MS
    else if (event.key === "Home") next = 0
    else if (event.key === "End") next = max
    if (next === null) return
    event.preventDefault()
    event.stopPropagation()
    onChange(clamp(next, 0, max))
  }

  const percent = max > 0 ? clamp(value / max, 0, 1) * 100 : 0
  const floating = hover

  return (
    <div
      role="slider"
      tabIndex={0}
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-valuenow={Math.round(value)}
      aria-valuetext={`${formatClock(value)} of ${formatClock(max)}`}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerUp}
      onPointerLeave={() => {
        if (!dragging.current) setHover(null)
      }}
      onKeyDown={onKeyDown}
      className={cn(
        "group relative flex h-5 cursor-pointer touch-none items-center rounded-sm outline-none focus-visible:ring-2 focus-visible:ring-ring",
        className
      )}
    >
      <div ref={trackRef} className="relative h-1.5 w-full rounded-full bg-muted">
        <div
          className="absolute inset-y-0 left-0 rounded-full bg-primary"
          style={{ width: `${percent}%` }}
        />
        <div
          className="absolute top-1/2 size-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-background bg-primary shadow-sm"
          style={{ left: `${percent}%` }}
        />
        {floating !== null ? (
          <div
            aria-hidden
            className="pointer-events-none absolute bottom-full mb-2 -translate-x-1/2 rounded-sm bg-popover px-1.5 py-0.5 text-xs text-popover-foreground shadow-sm ring-1 ring-border font-[family-name:var(--mini-font-data)] tabular-nums"
            style={{ left: `${max > 0 ? clamp(floating / max, 0, 1) * 100 : 0}%` }}
          >
            {formatClock(floating, true)}
          </div>
        ) : null}
      </div>
    </div>
  )
}
