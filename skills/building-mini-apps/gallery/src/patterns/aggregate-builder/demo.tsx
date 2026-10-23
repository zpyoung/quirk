import { useState } from "react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { useCollection } from "@/lib/mini/store"

import { AggregateBuilder } from "./aggregate-builder"
import type { FieldSchema } from "./types"

type Delivery = {
  id: string
  timestamp: number
  courier: string
  zone: string
  vehicle: string
  minutes: number
  km: number
  items: number
}

const SCHEMA: FieldSchema = {
  fields: [
    { key: "timestamp", label: "Time", kind: "time" },
    { key: "courier", label: "Courier", kind: "text" },
    { key: "zone", label: "Zone", kind: "text" },
    { key: "vehicle", label: "Vehicle", kind: "text" },
    { key: "minutes", label: "Minutes", kind: "number", unit: "min" },
    { key: "km", label: "Distance", kind: "number", unit: "km" },
    { key: "items", label: "Items", kind: "number" },
  ],
  timeField: "timestamp",
  barField: "minutes",
  rowLabel: "deliveries",
}

const HOUR = 3_600_000
const COURIERS = [
  { name: "Mika", vehicle: "bike" },
  { name: "Tobias", vehicle: "van" },
  { name: "Ines", vehicle: "scooter" },
  { name: "Oren", vehicle: "bike" },
  { name: "Sade", vehicle: "van" },
  { name: "Lucan", vehicle: "scooter" },
]
const ZONES = [
  { name: "Harbor", minutes: 22, km: 2.4 },
  { name: "Old Town", minutes: 27, km: 3.1 },
  { name: "Riverside", minutes: 31, km: 4.2 },
  { name: "Uptown", minutes: 35, km: 5.0 },
  { name: "Hillcrest", minutes: 41, km: 6.3 },
]
// relative order volume by hour of day: quiet nights, a lunch bump and a dinner peak
const HOUR_WEIGHT = [
  1, 1, 0, 0, 0, 1, 2, 3, 4, 4, 5, 8, 10, 8, 5, 4, 5, 8, 12, 12, 9, 6, 3, 2,
]

function mulberry32(seed: number) {
  let a = seed
  return () => {
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function buildSeed(): Delivery[] {
  const random = mulberry32(7)
  const end = Math.floor(Date.now() / HOUR) * HOUR
  const start = end - 48 * HOUR
  const hours: number[] = []
  for (let t = start; t < end; t += HOUR) {
    const weight = HOUR_WEIGHT[new Date(t).getHours()]
    for (let i = 0; i < weight * 2; i++) hours.push(t)
  }
  const rows = Array.from({ length: 1400 }, (_, index): Delivery => {
    const hour = hours[Math.floor(random() * hours.length)]
    const zone = ZONES[Math.floor(random() * ZONES.length)]
    const courier = COURIERS[Math.floor(random() * COURIERS.length)]
    const busy = HOUR_WEIGHT[new Date(hour).getHours()] >= 10 ? 1.4 : 1
    const spike = random() < 0.05 ? 2 + random() * 1.5 : 1
    const speed = courier.vehicle === "bike" ? 1.1 : courier.vehicle === "van" ? 0.95 : 1
    const minutes = zone.minutes * busy * spike * speed * (0.75 + random() * 0.5)
    return {
      id: `DL-${String(index + 1).padStart(4, "0")}`,
      timestamp: hour + Math.floor(random() * HOUR),
      courier: courier.name,
      zone: zone.name,
      vehicle: courier.vehicle,
      minutes: Math.round(minutes * 10) / 10,
      km: Math.round(zone.km * (0.7 + random() * 0.6) * 10) / 10,
      items: 1 + Math.floor(random() * 8),
    }
  })
  rows.sort((a, b) => a.timestamp - b.timestamp)
  return rows.map((row, i) => ({ ...row, id: `DL-${String(i + 1).padStart(4, "0")}` }))
}

type Preview = "live" | "empty" | "loading" | "error"
const PREVIEWS: Preview[] = ["live", "empty", "loading", "error"]
const PREVIEW_ERROR = new Error("The sample delivery log could not be read.")

export default function Demo() {
  const [seed] = useState(buildSeed)
  const store = useCollection<Delivery>("aggregate-builder-demo", seed)
  const [preview, setPreview] = useState<Preview>("live")
  const [opened, setOpened] = useState<Delivery | null>(null)

  const status =
    preview === "loading" || preview === "error"
      ? preview
      : store.status === "ready" || preview === "empty"
        ? "ready"
        : store.status
  const rows = preview === "empty" ? [] : store.items

  const restore = async () => {
    try {
      await store.replaceAll(buildSeed())
      setPreview("live")
    } catch (cause) {
      toast.error("Couldn't reset the sample deliveries", {
        description: cause instanceof Error ? cause.message : String(cause),
      })
    }
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-muted-foreground">State preview (demo only)</span>
        <div role="group" aria-label="State preview" className="flex gap-1">
          {PREVIEWS.map((name) => (
            <Button
              key={name}
              size="xs"
              variant={preview === name ? "default" : "outline"}
              aria-pressed={preview === name}
              onClick={() => {
                setPreview(name)
                setOpened(null)
              }}
              className="capitalize"
            >
              {name}
            </Button>
          ))}
        </div>
        <Button size="xs" variant="ghost" className="ml-auto" onClick={() => void restore()}>
          Reset sample data
        </Button>
      </div>

      <div className="min-h-[34rem] flex-1 overflow-hidden rounded-lg border">
        <AggregateBuilder
          rows={rows}
          schema={SCHEMA}
          status={status}
          error={preview === "error" ? PREVIEW_ERROR : store.error}
          onRetry={() => setPreview("live")}
          onOpenRow={setOpened}
          emptyTitle="No deliveries to chart"
          emptyAction={{ label: "Restore sample deliveries", onClick: () => void restore() }}
          aria-label="Delivery times"
        />
      </div>

      <p role="status" className="min-h-4 text-xs text-muted-foreground">
        {opened
          ? `${opened.id}: ${opened.courier} by ${opened.vehicle} to ${opened.zone}, ${opened.minutes} min, ${opened.km} km, ${opened.items} items.`
          : ""}
      </p>

      <p className="text-xs text-muted-foreground">
        Keys: v aggregate, g group by (Aggregates tab), s sort by, 1 Samples, 2 Aggregates, c line or
        bar. On the chart: Left and Right move the cursor, Home and End jump, Esc clears. Click a
        column header to sort by it; click a delivery ID to open it.
      </p>
    </div>
  )
}
