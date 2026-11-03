import { cn } from "@/lib/utils"

/**
 * Inline SVG line of `values`. Decorative (`aria-hidden`) unless `label` is
 * given, in which case it is an image with that text; the value itself should
 * always also be in text nearby.
 */
export function Sparkline({
  values,
  className,
  label,
}: {
  values: number[]
  className?: string
  label?: string
}) {
  if (values.length < 2) return null
  const min = Math.min(...values)
  const span = Math.max(...values) - min || 1
  const points = values
    .map((value, i) => {
      const x = (i / (values.length - 1)) * 100
      const y = 2 + (1 - (value - min) / span) * 20
      return `${x.toFixed(2)},${y.toFixed(2)}`
    })
    .join(" ")

  return (
    <svg
      viewBox="0 0 100 24"
      preserveAspectRatio="none"
      className={cn("h-6 w-full overflow-visible", className)}
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
    >
      <polyline
        points={points}
        fill="none"
        className="stroke-(--chart-1)"
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  )
}
