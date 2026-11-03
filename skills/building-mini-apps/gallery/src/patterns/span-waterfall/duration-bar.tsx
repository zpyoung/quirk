import { TriangleAlertIcon } from "lucide-react"

import { cn } from "@/lib/utils"

const LABEL_FLIPS_AT = 0.7
const ROOM_BEFORE_BAR = 0.25

/**
 * One span's bar on the shared axis. `left` and `width` are fractions of the
 * track. The duration label and error badge sit right of the bar, left of it
 * near the end of the track, or inside a bar that spans most of the track, so
 * a thin bar or a full-width one stays readable.
 */
export function DurationBar({
  left,
  width,
  color,
  label,
  errors = 0,
  className,
}: {
  left: number
  width: number
  color: string
  label: string
  errors?: number
  className?: string
}) {
  const end = left + width
  const crowded = end > LABEL_FLIPS_AT
  const inside = crowded && left <= ROOM_BEFORE_BAR
  const side = !crowded
    ? { left: `calc(${end * 100}% + 4px)` }
    : inside
      ? { right: "4px" }
      : { right: `calc(${(1 - left) * 100}% + 4px)` }
  return (
    <div className={cn("relative h-full", className)}>
      <div
        data-mini="bar"
        className="absolute top-1/2 h-4 min-w-[2px] -translate-y-1/2 rounded-sm"
        style={{ left: `${left * 100}%`, width: `${width * 100}%`, backgroundColor: color }}
      />
      <span
        className="absolute top-1/2 flex -translate-y-1/2 items-center gap-1 whitespace-nowrap"
        style={side}
      >
        {errors > 0 ? (
          <span
            data-mini="error-badge"
            aria-label={errors === 1 ? "1 error" : `${errors} errors`}
            className="inline-flex h-4 items-center gap-0.5 rounded-full bg-destructive px-1.5 text-[10px] leading-none font-medium text-background tabular-nums"
          >
            <TriangleAlertIcon className="size-2.5" aria-hidden />
            {errors}
          </span>
        ) : null}
        <span
          className={cn(
            "text-[11px] tabular-nums",
            inside ? "text-background" : "text-muted-foreground"
          )}
        >
          {label}
        </span>
      </span>
    </div>
  )
}
