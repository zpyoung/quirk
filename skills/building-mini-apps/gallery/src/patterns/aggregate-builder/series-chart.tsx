import { useEffect, useRef, useState, type PointerEvent } from "react"
import { useHotkeys } from "react-hotkeys-hook"

import { EmptyState } from "@/components/mini/states"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { cn } from "@/lib/utils"

import {
  INTERVAL_PRESETS,
  SERIES_DASHES,
  formatBucket,
  formatInterval,
  formatNumber,
  formatValue,
  type ChartModel,
} from "./aggregate"
import { FieldPicker, type FieldOption } from "./field-picker"
import type { AggregateQuery } from "./types"

const HEIGHT = 176
const MARGIN = { left: 44, right: 8, top: 8, bottom: 22 }
const AUTO = "auto"

const slotColor = (slot: number) => `var(--chart-${slot + 1})`

function useWidth() {
  const ref = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(560)
  useEffect(() => {
    const node = ref.current
    if (!node) return
    const observer = new ResizeObserver(([entry]) => {
      setWidth(Math.max(240, Math.round(entry.contentRect.width)))
    })
    observer.observe(node)
    return () => observer.disconnect()
  }, [])
  return [ref, width] as const
}

function linePaths(values: (number | null)[], x: (i: number) => number, y: (v: number) => number) {
  const paths: string[] = []
  const dots: { x: number; y: number }[] = []
  let run: string[] = []
  const flush = (end: number) => {
    if (run.length === 1) {
      const start = end - 1
      dots.push({ x: x(start), y: y(values[start] as number) })
    } else if (run.length > 1) {
      paths.push(run.join(" "))
    }
    run = []
  }
  values.forEach((value, i) => {
    if (value === null) return flush(i)
    run.push(`${run.length === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(value).toFixed(1)}`)
  })
  flush(values.length)
  return { paths, dots }
}

/**
 * Inline SVG line or bar chart of a ChartModel, one series per group in the chart tokens, with a
 * header (title, chart type, interval), a legend, a cursor with a value box, and a footnote. The
 * plot is a slider over buckets so Left, Right, Home, End and Esc work from the keyboard.
 */
export function SeriesChart({
  model,
  title,
  unit,
  query,
  onChange,
  noValuesLabel,
}: {
  model: ChartModel | null
  title: string
  unit?: string
  query: AggregateQuery
  onChange: (patch: Partial<AggregateQuery>) => void
  noValuesLabel: string
}) {
  const [measureRef, width] = useWidth()
  const [cursor, setCursor] = useState<number | null>(null)
  const count = model?.buckets.length ?? 0
  const active = cursor !== null && cursor < count ? cursor : null

  const plotRef = useHotkeys<HTMLDivElement>(
    "left,right,home,end,esc",
    (event) => {
      if (count === 0) return
      if (event.key === "Escape") return setCursor(null)
      if (event.key === "Home") return setCursor(0)
      if (event.key === "End") return setCursor(count - 1)
      const step = event.key === "ArrowLeft" ? -1 : 1
      setCursor((current) => {
        if (current === null) return step === 1 ? 0 : count - 1
        return Math.min(count - 1, Math.max(0, current + step))
      })
    },
    // the plot is role=slider, which the hook treats as a form control and skips by default
    { enabled: count > 0, preventDefault: true, enableOnFormTags: ["slider"] }
  )

  const intervalOptions: FieldOption[] = [
    { value: AUTO, label: model ? `Auto (${formatInterval(model.interval)})` : "Auto" },
    ...INTERVAL_PRESETS.map((preset) => ({
      value: String(preset),
      label: formatInterval(preset),
    })),
  ]

  const header = (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
      <h3 className="min-w-0 flex-1 truncate text-sm font-medium">{title}</h3>
      <ToggleGroup
        type="single"
        variant="outline"
        size="sm"
        value={query.chart}
        onValueChange={(next) => next && onChange({ chart: next as "line" | "bar" })}
        aria-label="Chart type"
      >
        <ToggleGroupItem value="line">Line</ToggleGroupItem>
        <ToggleGroupItem value="bar">Bar</ToggleGroupItem>
      </ToggleGroup>
      <div className="w-36">
        <FieldPicker
          label="Interval"
          value={query.interval === null ? AUTO : String(query.interval)}
          onChange={(next) => onChange({ interval: next === null || next === AUTO ? null : Number(next) })}
          options={intervalOptions}
        />
      </div>
    </div>
  )

  if (!model || !model.hasValues) {
    return (
      <div className="flex flex-col gap-2 p-3">
        {header}
        <div ref={measureRef} className="w-full">
          <EmptyState
            title={model ? noValuesLabel : "No row has a time"}
            description={
              model
                ? "Pick another field or aggregate."
                : "The chart places rows by their time field, so there is nothing to draw."
            }
          />
        </div>
      </div>
    )
  }

  const plotW = width - MARGIN.left - MARGIN.right
  const plotH = HEIGHT - MARGIN.top - MARGIN.bottom
  const slot = plotW / count
  const x = (i: number) => MARGIN.left + (i + 0.5) * slot
  const y = (value: number) => MARGIN.top + plotH - (value / model.yMax) * plotH
  const multiDay = model.buckets[count - 1] - model.buckets[0] >= 24 * 3_600_000
  const labelEvery = Math.max(1, Math.ceil(count / Math.max(2, Math.floor(plotW / 96))))
  const bucketLabel = (i: number, withDate: boolean) =>
    formatBucket(model.buckets[i], model.interval, withDate)

  const valueText =
    active === null
      ? "No bucket selected. Use the arrow keys to read a bucket."
      : `${bucketLabel(active, true)}: ${model.series
          .map((series) => `${series.label} ${formatValue(series.values[active], unit)}`)
          .join(", ")}`

  const onPointerMove = (event: PointerEvent<HTMLDivElement>) => {
    const box = event.currentTarget.getBoundingClientRect()
    const offset = event.clientX - box.left - MARGIN.left
    if (offset < 0 || offset > plotW) return setCursor(null)
    setCursor(Math.min(count - 1, Math.floor(offset / slot)))
  }

  const stackedBase = new Array(count).fill(0) as number[]

  return (
    <figure
      className="m-0 flex flex-col gap-2 p-3"
      aria-label={`${title}, ${count} buckets of ${formatInterval(model.interval)}, ${model.series.length} series`}
    >
      {header}
      <ul className="m-0 flex list-none flex-wrap gap-x-3 gap-y-1 p-0 text-xs text-muted-foreground">
        {model.series.map((series) => (
          <li key={series.slot} className="flex min-w-0 items-center gap-1.5">
            <svg width="18" height="8" aria-hidden className="shrink-0">
              {query.chart === "line" ? (
                <line
                  x1="0"
                  x2="18"
                  y1="4"
                  y2="4"
                  strokeWidth="2"
                  strokeDasharray={SERIES_DASHES[series.slot]}
                  style={{ stroke: slotColor(series.slot) }}
                />
              ) : (
                <rect width="18" height="8" rx="1" style={{ fill: slotColor(series.slot) }} />
              )}
            </svg>
            <span className="truncate">{series.label}</span>
          </li>
        ))}
      </ul>
      <div ref={measureRef} className="w-full">
        <div
          ref={plotRef}
          role="slider"
          tabIndex={0}
          aria-label="Chart cursor"
          aria-orientation="horizontal"
          aria-valuemin={0}
          aria-valuemax={count - 1}
          aria-valuenow={active ?? 0}
          aria-valuetext={valueText}
          onPointerMove={onPointerMove}
          onPointerLeave={() => setCursor(null)}
          onBlur={() => setCursor(null)}
          className="relative rounded-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
          style={{ height: HEIGHT }}
        >
          <svg width={width} height={HEIGHT} aria-hidden className="block overflow-visible">
            {model.yTicks.map((tick) => (
              <g key={tick}>
                <line
                  x1={MARGIN.left}
                  x2={width - MARGIN.right}
                  y1={y(tick)}
                  y2={y(tick)}
                  className="stroke-border"
                  strokeWidth={1}
                />
                <text
                  x={MARGIN.left - 6}
                  y={y(tick)}
                  textAnchor="end"
                  dominantBaseline="middle"
                  fontSize={10}
                  className="fill-muted-foreground"
                >
                  {formatNumber(tick)}
                </text>
              </g>
            ))}
            {model.buckets.map((_, i) =>
              i % labelEvery === 0 ? (
                <text
                  key={i}
                  x={x(i)}
                  y={HEIGHT - 6}
                  textAnchor="middle"
                  fontSize={10}
                  className="fill-muted-foreground"
                >
                  {bucketLabel(i, multiDay)}
                </text>
              ) : null
            )}

            {query.chart === "bar"
              ? model.series.map((series, seriesIndex) =>
                  series.values.map((value, i) => {
                    if (value === null || value <= 0) return null
                    const k = model.stacked ? 1 : model.series.length
                    const barW = Math.max(1, (slot * 0.8) / k)
                    const left = MARGIN.left + i * slot + slot * 0.1 + (model.stacked ? 0 : seriesIndex * barW)
                    const base = model.stacked ? stackedBase[i] : 0
                    const top = y(base + value)
                    if (model.stacked) stackedBase[i] += value
                    return (
                      <rect
                        key={`${series.slot}-${i}`}
                        x={left}
                        y={top}
                        width={Math.max(1, barW - (barW > 3 ? 1 : 0))}
                        height={Math.max(0, y(base) - top)}
                        style={{ fill: slotColor(series.slot) }}
                      />
                    )
                  })
                )
              : model.series.map((series) => {
                  const { paths, dots } = linePaths(series.values, x, y)
                  const color = slotColor(series.slot)
                  return (
                    <g key={series.slot}>
                      {paths.map((d) => (
                        <path
                          key={d}
                          d={d}
                          fill="none"
                          strokeWidth={1.75}
                          strokeLinejoin="round"
                          strokeLinecap="round"
                          strokeDasharray={SERIES_DASHES[series.slot]}
                          style={{ stroke: color }}
                        />
                      ))}
                      {dots.map((dot) => (
                        <circle key={dot.x} cx={dot.x} cy={dot.y} r={2.5} style={{ fill: color }} />
                      ))}
                    </g>
                  )
                })}

            {active !== null ? (
              <g>
                <line
                  x1={x(active)}
                  x2={x(active)}
                  y1={MARGIN.top}
                  y2={MARGIN.top + plotH}
                  className="stroke-muted-foreground"
                  strokeWidth={1}
                />
                {query.chart === "line"
                  ? model.series.map((series) => {
                      const value = series.values[active]
                      return value === null ? null : (
                        <circle
                          key={series.slot}
                          cx={x(active)}
                          cy={y(value)}
                          r={3.5}
                          className="stroke-background"
                          strokeWidth={1.5}
                          style={{ fill: slotColor(series.slot) }}
                        />
                      )
                    })
                  : null}
              </g>
            ) : null}
          </svg>

          {active !== null ? (
            <div
              className={cn(
                "pointer-events-none absolute top-2 z-10 min-w-36 rounded-md border bg-popover p-2 text-xs text-popover-foreground shadow-md",
                active > count / 2 ? "-translate-x-full" : ""
              )}
              style={{ left: x(active) + (active > count / 2 ? -8 : 8) }}
            >
              <p className="mb-1 font-medium">{bucketLabel(active, true)}</p>
              <ul className="m-0 flex list-none flex-col gap-0.5 p-0">
                {model.series.map((series) => (
                  <li key={series.slot} className="flex items-center gap-1.5">
                    <span
                      aria-hidden
                      className="size-2 shrink-0 rounded-[2px]"
                      style={{ background: slotColor(series.slot) }}
                    />
                    <span className="min-w-0 flex-1 truncate">{series.label}</span>
                    <span className="font-[family-name:var(--mini-font-data)] tabular-nums">
                      {formatValue(series.values[active], unit)}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      </div>
      <figcaption className="text-xs text-muted-foreground">
        {model.rowCount} {model.rowCount === 1 ? "row" : "rows"} in {count}{" "}
        {count === 1 ? "bucket" : "buckets"} of {formatInterval(model.interval)}
      </figcaption>
    </figure>
  )
}
