import { formatCount, trendBars } from "./trend"

/**
 * Small bar histogram of `values` in an inline SVG, with a dashed line at the
 * peak, the peak value at the top right and an optional state word under it.
 * `label` names the series for assistive tech; the peak is appended.
 */
export function TrendCell({
  values,
  caption,
  label = "Trend",
}: {
  values: number[]
  caption?: string
  label?: string
}) {
  const { peak, bars } = trendBars(values)
  return (
    <div className="flex w-full flex-col gap-0.5">
      <div className="flex items-start gap-1.5">
        <svg
          viewBox="0 0 100 24"
          preserveAspectRatio="none"
          role="img"
          aria-label={`${label}, peak ${formatCount(peak)}`}
          className="h-6 min-w-0 flex-1 overflow-visible"
        >
          <line
            x1="0"
            x2="100"
            y1="0.5"
            y2="0.5"
            className="stroke-border"
            strokeDasharray="2 2"
            vectorEffect="non-scaling-stroke"
          />
          {bars.map((bar, index) =>
            bar.height > 0 ? (
              <rect
                key={index}
                x={bar.x}
                y={24 - bar.height}
                width={bar.width}
                height={bar.height}
                className="fill-(--chart-1)"
              />
            ) : null
          )}
        </svg>
        <span
          aria-hidden
          className="text-[10px] leading-none text-muted-foreground tabular-nums"
        >
          {formatCount(peak)}
        </span>
      </div>
      {caption ? (
        <span className="text-xs text-muted-foreground">{caption}</span>
      ) : null}
    </div>
  )
}
