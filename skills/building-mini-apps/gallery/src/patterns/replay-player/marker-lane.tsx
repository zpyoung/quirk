import { cn } from "@/lib/utils"

import { formatClock } from "./playback"
import type { ReplayMarker } from "./types"

const SHAPES: Record<string, string> = {
  click: "size-2 rounded-full bg-primary",
  navigation: "size-2 rotate-45 rounded-[1px] bg-muted-foreground",
  error: "h-3 w-1.5 rounded-[1px] bg-destructive",
}

/** One mark per event over the seek slider, with a playhead line. Marks are pointer-only: the skip button and the list times reach the same moments from the keyboard. */
export function MarkerLane({
  markers,
  durationMs,
  time,
  onSeek,
  className,
}: {
  markers: ReplayMarker[]
  durationMs: number
  time: number
  onSeek: (ms: number) => void
  className?: string
}) {
  const playhead = durationMs > 0 ? Math.min(1, time / durationMs) * 100 : 0
  return (
    <div aria-hidden className={cn("relative h-4 w-full", className)}>
      <div
        className="absolute inset-y-0 w-px -translate-x-1/2 bg-primary"
        style={{ left: `${playhead}%` }}
      />
      {markers.map((marker) => (
        <button
          key={marker.id}
          type="button"
          tabIndex={-1}
          title={`${marker.kind} at ${formatClock(marker.at)}`}
          onClick={() => onSeek(marker.at)}
          className="absolute top-1/2 flex size-4 -translate-x-1/2 -translate-y-1/2 cursor-pointer items-center justify-center"
          style={{ left: `${marker.percent}%` }}
        >
          <span className={cn("block", SHAPES[marker.kind] ?? SHAPES.click)} />
        </button>
      ))}
    </div>
  )
}
