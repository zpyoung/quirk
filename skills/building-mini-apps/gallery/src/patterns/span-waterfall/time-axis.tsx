import { formatDuration } from "./waterfall"
import type { Scale, WaterfallMarker } from "./types"

const pct = (fraction: number) => `${fraction * 100}%`

const HATCH = "repeating-linear-gradient(135deg, var(--border) 0 1px, transparent 1px 6px)"

/** Where to anchor a label that sits at `at`: left-aligned, or right-aligned near the end of the axis. */
const anchor = (at: number) => (at > 0.9 ? "translateX(calc(-100% - 4px))" : "translateX(4px)")

/**
 * Header row over the timeline: tick labels, marker flags, and a labeled pill
 * over each squeezed gap showing how much time it hides.
 */
export function TimeAxis({
  scale,
  markers = [],
}: {
  scale: Scale
  markers?: WaterfallMarker[]
}) {
  return (
    <div
      data-mini="axis"
      className={`relative overflow-hidden ${markers.length > 0 ? "h-10" : "h-7"}`}
    >
      {scale.ticks.map((tick) => (
        <div key={tick.t} className="absolute inset-y-0" style={{ left: pct(tick.at) }}>
          <span className="absolute inset-y-0 w-px bg-border/60" aria-hidden />
          <span
            className="absolute bottom-1 text-[10px] whitespace-nowrap text-muted-foreground tabular-nums"
            style={{ transform: anchor(tick.at) }}
          >
            {tick.label}
          </span>
        </div>
      ))}
      {scale.gaps.map((gap) => (
        <div
          key={gap.from}
          className="absolute bottom-1 -translate-x-1/2"
          style={{ left: pct(gap.at + gap.width / 2) }}
        >
          <span
            title={`${formatDuration(gap.to - gap.from)} with nothing running, squeezed`}
            className="rounded-full border bg-background px-1.5 text-[10px] whitespace-nowrap text-muted-foreground tabular-nums"
          >
            {formatDuration(gap.to - gap.from)}
            <span className="sr-only"> of idle time squeezed</span>
          </span>
        </div>
      ))}
      {markers.map((marker) => {
        const at = scale.position(marker.at)
        return (
          <span
            key={`${marker.label}-${marker.at}`}
            className="absolute top-0.5 rounded-full border border-primary/50 bg-background px-1.5 text-[10px] leading-4 whitespace-nowrap"
            style={{
              left: pct(at),
              transform: at > 0.9 ? "translateX(-100%)" : at < 0.05 ? "none" : "translateX(-50%)",
            }}
          >
            {marker.label}
          </span>
        )
      })}
    </div>
  )
}

/**
 * Full-height guides behind the rows, aligned with `TimeAxis`: tick lines,
 * dashed marker lines and a hatched band for each squeezed gap.
 */
export function TimeGuides({
  scale,
  markers = [],
}: {
  scale: Scale
  markers?: WaterfallMarker[]
}) {
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0">
      {scale.ticks.map((tick) => (
        <span
          key={tick.t}
          className="absolute inset-y-0 w-px bg-border/40"
          style={{ left: pct(tick.at) }}
        />
      ))}
      {scale.gaps.map((gap) => (
        <span
          key={gap.from}
          className="absolute inset-y-0 border-x border-border bg-muted/30"
          style={{ left: pct(gap.at), width: pct(gap.width), backgroundImage: HATCH }}
        />
      ))}
      {markers.map((marker) => (
        <span
          key={`${marker.label}-${marker.at}`}
          className="absolute inset-y-0 border-l border-dashed border-primary/60"
          style={{ left: pct(scale.position(marker.at)) }}
        />
      ))}
    </div>
  )
}
