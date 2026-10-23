import { useMemo, useState } from "react"

import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { useCollection } from "@/lib/mini/store"

import { MiniFull } from "./index"

type DemoTag = "home" | "work" | "health"

type DemoEvent = {
  id: string
  title: string
  start: string
  end?: string
  allDay: boolean
  tag?: DemoTag
}

type Preview = "live" | "empty" | "loading" | "error"

const TAGS: DemoTag[] = ["home", "work", "health"]

function at(dayOffset: number, time?: string, minutes = 30): Omit<DemoEvent, "id" | "title" | "tag"> {
  const base = new Date()
  const day = new Date(base.getFullYear(), base.getMonth(), base.getDate() + dayOffset)
  if (!time) return { start: day.toISOString(), allDay: true }
  const [h, m] = time.split(":").map(Number)
  const start = new Date(day.getFullYear(), day.getMonth(), day.getDate(), h, m)
  return {
    start: start.toISOString(),
    end: new Date(start.getTime() + minutes * 60_000).toISOString(),
    allDay: false,
  }
}

function makeSeed(): DemoEvent[] {
  return [
    { id: "seed-1", title: "Pick up dry cleaning", tag: "home", ...at(-2, "17:00") },
    { id: "seed-2", title: "Standup", tag: "work", ...at(0, "09:00") },
    { id: "seed-3", title: "Dentist", tag: "health", ...at(0, "14:00", 60) },
    { id: "seed-4", title: "Water the plants", tag: "home", ...at(0) },
    { id: "seed-5", title: "Lunch with Sam", ...at(1, "12:00", 60) },
    { id: "seed-6", title: "Call landlord", tag: "home", ...at(1, "16:30") },
    {
      id: "seed-7",
      title: "Renew the annual parking permit at the city office before the late fee applies",
      ...at(2, "10:00", 45),
    },
    { id: "seed-8", title: "Yoga", tag: "health", ...at(4, "18:30", 90) },
    { id: "seed-9", title: "Pay quarterly taxes", tag: "work", ...at(8) },
    { id: "seed-10", title: "Quarterly planning", tag: "work", ...at(12, "09:30", 60) },
    { id: "seed-11", title: "Car service", tag: "home", ...at(19, "15:00", 120) },
    { id: "seed-12", title: "Renew passport", ...at(27) },
  ]
}

const PREVIEWS: { value: Preview; label: string }[] = [
  { value: "live", label: "Live" },
  { value: "empty", label: "Empty" },
  { value: "loading", label: "Loading" },
  { value: "error", label: "Error" },
]

export default function Demo() {
  const seed = useMemo(() => makeSeed(), [])
  const events = useCollection<DemoEvent>("mini-full-demo", seed)
  const [preview, setPreview] = useState<Preview>("live")

  const status = preview === "loading" ? "loading" : preview === "error" ? "error" : events.status
  const items = preview === "empty" ? [] : events.items

  return (
    <div className="flex h-full min-h-[40rem] flex-col">
      <div className="flex shrink-0 items-center gap-2 border-b px-3 py-2 text-xs">
        <span className="text-muted-foreground">Preview state</span>
        <ToggleGroup
          type="multiple"
          variant="outline"
          size="sm"
          value={[preview]}
          onValueChange={(next) => {
            const picked = next.find((v) => v !== preview)
            if (picked) setPreview(picked as Preview)
          }}
          aria-label="Preview state"
          rovingFocus={false}
        >
          {PREVIEWS.map(({ value, label }) => (
            <ToggleGroupItem key={value} value={value} aria-label={`${label} state`}>
              {label}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      </div>
      <div className="min-h-0 flex-1 p-3">
        <MiniFull<DemoEvent>
          items={items}
          status={status}
          error={preview === "error" ? new Error("Could not read appointments from this browser.") : events.error}
          onRetry={() => setPreview("live")}
          getStart={(e) => new Date(e.start)}
          getEnd={(e) => (e.end && !e.allDay ? new Date(e.end) : undefined)}
          getTag={(e) => e.tag}
          tags={TAGS}
          emptyHint='Try "dentist tomorrow at 10-11" or "call landlord fri /home".'
          fromEntry={(entry) => ({
            title: entry.title,
            start: (entry.start ?? new Date()).toISOString(),
            end: entry.end?.toISOString(),
            allDay: entry.allDay,
            tag: TAGS.find((t) => t === entry.tag),
          })}
          onAdd={async (item) => {
            await events.add({ id: crypto.randomUUID(), ...item })
            if (preview === "empty") setPreview("live")
          }}
          onRemove={events.remove}
        />
      </div>
    </div>
  )
}
