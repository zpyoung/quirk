import { useState } from "react"
import { CalendarIcon, TagIcon } from "lucide-react"

import { EmptyState, ErrorState, LoadingState } from "@/components/mini/states"
import { Button } from "@/components/ui/button"
import { useCollection } from "@/lib/mini/store"
import { DateField, ExpandList, TextField, type ExpandItem } from "./index"

type Task = ExpandItem & { due?: string; tags?: string }

function daysFromToday(offset: number): string {
  const date = new Date()
  date.setDate(date.getDate() + offset)
  const pad = (n: number) => String(n).padStart(2, "0")
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

const seed: Task[] = [
  { id: "t1", title: "Buy oat milk" },
  { id: "t2", title: "Return library books", due: daysFromToday(1) },
  { id: "t3", title: "Pick up dry cleaning", tags: "errand" },
  {
    id: "t4",
    title: "Renew passport",
    due: daysFromToday(14),
    notes:
      "Bring two photos and the old passport. Appointment needs booking online first.",
  },
  { id: "t5", title: "Book dentist", due: daysFromToday(6) },
  { id: "t6", title: "Mail parcel to Sam", tags: "post, errand" },
  {
    id: "t7",
    title:
      "Compare quotes for replacing the back-door lock, the garden gate latch and the side-window handles before the landlord's inspection",
  },
  { id: "t8", title: "Water the plants" },
]

const fields = [
  DateField<Task>("due", "Due date", <CalendarIcon />),
  TextField<Task>("tags", "Tags", <TagIcon />),
]

const previews = ["live", "empty", "loading", "error"] as const
type Preview = (typeof previews)[number]

function StatePreview({
  preview,
  onExit,
}: {
  preview: Exclude<Preview, "live">
  onExit(): void
}) {
  if (preview === "loading") return <LoadingState label="Loading items" />
  if (preview === "error") {
    return (
      <ErrorState
        error={new Error("Could not read the saved items")}
        onRetry={onExit}
      />
    )
  }
  return (
    <EmptyState
      title="Nothing here yet"
      description="Press N to add an item"
      action={
        <Button size="sm" onClick={onExit}>
          Back to live list
        </Button>
      }
    />
  )
}

export default function Demo() {
  const [preview, setPreview] = useState<Preview>("live")
  const { replaceAll } = useCollection<Task>("expand-in-place-demo", seed)

  const toolbar = (
    <div
      role="group"
      aria-label="State preview (demo only)"
      className="flex items-center gap-1"
    >
      <span className="text-xs text-muted-foreground">Preview state</span>
      {previews.map((name) => (
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
      <Button size="xs" variant="outline" onClick={() => void replaceAll(seed)}>
        Reset sample data
      </Button>
    </div>
  )

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex h-10 shrink-0 items-center gap-3 border-b px-3">
        <h2 data-mini="title" className="text-sm font-semibold tracking-tight">Errands</h2>
        <div className="ml-auto">{toolbar}</div>
      </header>
      <div className="min-h-0 flex-1 overflow-auto">
        {preview === "live" ? (
          <ExpandList<Task>
            collection="expand-in-place-demo"
            seed={seed}
            fields={fields}
            newItem={() => ({ id: crypto.randomUUID(), title: "" })}
            emptyTitle="No errands yet"
          />
        ) : (
          <StatePreview preview={preview} onExit={() => setPreview("live")} />
        )}
      </div>
    </div>
  )
}
