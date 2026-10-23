import { useState } from "react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { useCollection } from "@/lib/mini/store"

import { ViewSwitcher } from "./view-switcher"
import type { FieldDef, ViewConfig } from "./types"

const STAGES = ["Idea", "Planned", "Confirmed", "Done"]
const HOSTS = ["Mira Okafor", "Jonas Reyes", "Priya Nair"]

interface Workshop {
  id: string
  title: string
  stage: string
  host?: string
  date?: string
  seats?: number
}

const FIELDS: FieldDef<Workshop>[] = [
  { key: "stage", label: "Stage", type: "select", options: STAGES },
  { key: "host", label: "Host", type: "select", options: HOSTS },
  { key: "date", label: "Date", type: "date" },
  { key: "seats", label: "Seats", type: "number" },
]

const VIEWS: ViewConfig[] = [
  { id: "all", name: "All", layout: "table", filters: [] },
  {
    id: "calendar",
    name: "Calendar",
    layout: "calendar",
    filters: [],
    dateField: "date",
  },
  {
    id: "by-stage",
    name: "By stage",
    layout: "board",
    filters: [],
    groupBy: "stage",
  },
  {
    id: "upcoming",
    name: "Upcoming",
    layout: "list",
    filters: [{ field: "stage", op: "anyOf", value: ["Planned", "Confirmed"] }],
    sort: { field: "date", dir: "asc" },
  },
]

function dayOfThisMonth(day: number): string {
  const now = new Date()
  const pad = (n: number) => String(n).padStart(2, "0")
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(day)}`
}

function buildSeed(): Workshop[] {
  return [
    {
      id: "w1",
      title: "Intro to linocut printing",
      stage: "Confirmed",
      host: HOSTS[0],
      date: dayOfThisMonth(3),
      seats: 12,
    },
    {
      id: "w2",
      title: "Sourdough basics",
      stage: "Done",
      host: HOSTS[1],
      date: dayOfThisMonth(5),
      seats: 8,
    },
    {
      id: "w3",
      title: "Watercolor for beginners",
      stage: "Planned",
      host: HOSTS[2],
      date: dayOfThisMonth(9),
      seats: 15,
    },
    {
      id: "w4",
      title: "Mending and visible repair",
      stage: "Planned",
      host: HOSTS[0],
      date: dayOfThisMonth(9),
      seats: 10,
    },
    {
      id: "w5",
      title: "Plant propagation swap",
      stage: "Confirmed",
      host: HOSTS[2],
      date: dayOfThisMonth(9),
      seats: 20,
    },
    {
      id: "w6",
      title: "Zine making night",
      stage: "Planned",
      host: HOSTS[1],
      date: dayOfThisMonth(9),
      seats: 14,
    },
    {
      id: "w7",
      title: "Cyanotype sun prints",
      stage: "Idea",
      host: HOSTS[0],
      date: dayOfThisMonth(14),
      seats: 9,
    },
    {
      id: "w8",
      title: "Beekeeping for the curious",
      stage: "Confirmed",
      host: HOSTS[2],
      date: dayOfThisMonth(18),
      seats: 25,
    },
    {
      id: "w9",
      title: "Pasta by hand",
      stage: "Planned",
      host: HOSTS[1],
      date: dayOfThisMonth(21),
      seats: 12,
    },
    {
      id: "w10",
      title: "Bookbinding: the long-stitch spine",
      stage: "Done",
      host: HOSTS[0],
      date: dayOfThisMonth(25),
      seats: 8,
    },
    {
      id: "w11",
      title:
        "An unusually thorough afternoon on the history, chemistry and practical craft of natural dyes from kitchen scraps",
      stage: "Idea",
      host: HOSTS[2],
      date: dayOfThisMonth(27),
      seats: 18,
    },
    {
      id: "w12",
      title: "Open studio and critique",
      stage: "Planned",
      date: dayOfThisMonth(28),
      seats: 30,
    },
    {
      id: "w13",
      title: "Foraging walk",
      stage: "Idea",
      host: HOSTS[1],
      seats: 16,
    },
    { id: "w14", title: "Soldering workshop", stage: "Idea", host: HOSTS[0] },
  ]
}

/** Surfaces a rejected storage write as a toast instead of an unhandled rejection. */
function reportWrite(write: Promise<void>, action: string): void {
  write.catch((cause: unknown) => {
    toast.error(`Couldn't ${action} the workshop`, {
      description: cause instanceof Error ? cause.message : String(cause),
    })
  })
}

type Preview = "live" | "empty" | "loading" | "error"
const PREVIEWS: Preview[] = ["live", "empty", "loading", "error"]

export default function Demo() {
  const workshops = useCollection<Workshop>("view-switcher-demo", buildSeed())
  const [preview, setPreview] = useState<Preview>("live")

  const status =
    preview === "loading"
      ? "loading"
      : preview === "error"
        ? "error"
        : workshops.status
  const items = preview === "empty" ? [] : workshops.items

  return (
    <div className="flex h-full min-h-[34rem] flex-col">
      <div className="flex shrink-0 flex-wrap items-center gap-2 border-b px-3 py-1.5">
        <h2 data-mini="title" className="text-sm font-semibold">Workshop planner</h2>
        <div
          role="group"
          aria-label="Preview state"
          className="ml-auto flex items-center gap-1"
        >
          <span className="text-xs text-muted-foreground">Preview state</span>
          {PREVIEWS.map((name) => (
            <Button
              key={name}
              size="xs"
              variant={preview === name ? "secondary" : "ghost"}
              aria-pressed={preview === name}
              onClick={() => setPreview(name)}
            >
              {name}
            </Button>
          ))}
        </div>
      </div>
      <div className="min-h-0 flex-1">
        <ViewSwitcher
          items={items}
          fields={FIELDS}
          storageKey="view-switcher-demo"
          defaultViews={VIEWS}
          noun="workshop"
          status={status}
          error={
            new Error("The workshop list couldn't be read from this browser.")
          }
          onRetry={() => setPreview("live")}
          onCreate={(defaults) =>
            reportWrite(
              workshops.add({
                stage: "Idea",
                ...defaults,
                id: crypto.randomUUID(),
                title: "New workshop",
              }),
              "add",
            )
          }
          onUpdate={(id, patch) =>
            reportWrite(workshops.update(id, patch), "update")
          }
          onDelete={(id) => reportWrite(workshops.remove(id), "delete")}
        />
      </div>
    </div>
  )
}
