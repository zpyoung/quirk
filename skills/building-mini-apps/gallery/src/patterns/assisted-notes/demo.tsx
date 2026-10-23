import { useState } from "react"

import { EmptyState, ErrorState, LoadingState } from "@/components/mini/states"
import { Button } from "@/components/ui/button"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"

import { AssistedNotes, type AssistedNoteItem, type NoteSegment } from "./index"

type GardenNote = AssistedNoteItem & { transcript: string }

const user = (
  id: string,
  text: string,
  kind?: NoteSegment["kind"]
): NoteSegment => ({
  id,
  origin: "user",
  text,
  kind,
})

const generated = (
  id: string,
  text: string,
  after: string | undefined,
  excerpt?: string,
  summary?: string
): NoteSegment => ({
  id,
  origin: "generated",
  text,
  after,
  source: excerpt ? { excerpt, label: "Transcript", summary } : undefined,
})

const seed: GardenNote[] = [
  {
    id: "spring-planting",
    title: "Spring planting day",
    transcript:
      "We start at nine with coffee and a walk through the beds. Mina will bring forty tomato seedlings and the twine. Kids from the school can take the sunflower row by the fence. We need two more wheelbarrows before Saturday. Lunch is a potluck under the pergola, so please sign up for a dish.",
    segments: [
      user("sp-1", "Spring planting day", "heading"),
      user("sp-2", "Start at 9, coffee first"),
      generated(
        "sp-3",
        "Walk the beds together before planting",
        "sp-2",
        "We start at nine with coffee and a walk through the beds.",
        "Drafted from the opening of the call."
      ),
      user("sp-4", "Mina: tomato seedlings + twine"),
      generated(
        "sp-5",
        "Mina brings 40 tomato seedlings and the twine",
        "sp-4",
        "Mina will bring forty tomato seedlings and the twine.",
        "Quantity taken from the transcript."
      ),
      user("sp-6", "School kids on the sunflower row"),
      generated(
        "sp-7",
        "Sunflower row by the fence is the kids' job",
        "sp-6",
        "Kids from the school can take the sunflower row by the fence."
      ),
      user("sp-8", "Need wheelbarrows"),
      generated(
        "sp-9",
        "Two more wheelbarrows needed before Saturday",
        "sp-8",
        "We need two more wheelbarrows before Saturday.",
        "Deadline added from the transcript."
      ),
      user("sp-10", "Potluck lunch, sign-up sheet"),
    ],
  },
  {
    id: "tool-shed",
    title: "Tool shed inventory",
    transcript:
      "The shed has six spades but only two have sound handles. The hose reel leaks at the connector near the tap. We are out of gloves in small and medium sizes. Someone should oil the pruning shears before the roses need cutting.",
    segments: [
      user("ts-1", "Shed check", "heading"),
      user("ts-2", "6 spades, handles iffy"),
      generated(
        "ts-3",
        "Only two of the six spades have sound handles",
        "ts-2",
        "The shed has six spades but only two have sound handles."
      ),
      user("ts-4", "Hose reel leaking"),
      generated(
        "ts-5",
        "Leak is at the connector near the tap",
        "ts-4",
        "The hose reel leaks at the connector near the tap.",
        "Location of the leak."
      ),
      user("ts-6", "Gloves"),
      generated(
        "ts-7",
        "Small and medium gloves are out of stock",
        "ts-6",
        "We are out of gloves in small and medium sizes."
      ),
      user("ts-8", "Oil the shears before the roses"),
    ],
  },
  {
    id: "sign-ups",
    title: "Volunteer sign-ups",
    transcript:
      "Eleven people have signed up for the morning shift. The afternoon shift is short by four, mostly because of the football match. Priya can lead the compost team if someone covers the welcome table. Two newcomers asked whether they need to bring their own tools. We should send a reminder email on Thursday evening, not Friday morning.",
    segments: [
      user("vs-1", "Sign-ups so far", "heading"),
      user("vs-2", "Morning: 11"),
      user("vs-3", "Afternoon: short"),
      generated(
        "vs-4",
        "Afternoon shift is short by four people",
        "vs-3",
        "The afternoon shift is short by four, mostly because of the football match.",
        "The football match is the likely cause."
      ),
      user("vs-5", "Leads", "heading"),
      user("vs-6", "Priya on compost"),
      generated(
        "vs-7",
        "Priya leads compost if the welcome table is covered",
        "vs-6",
        "Priya can lead the compost team if someone covers the welcome table."
      ),
      user("vs-8", "Welcome table: open"),
      user("vs-9", "Newcomers"),
      generated(
        "vs-10",
        "Two newcomers asked whether to bring tools",
        "vs-9",
        "Two newcomers asked whether they need to bring their own tools."
      ),
      generated(
        "vs-11",
        "Send the reminder Thursday evening, not Friday morning",
        undefined,
        "We should send a reminder email on Thursday evening, not Friday morning."
      ),
      user("vs-12", "Reminder email"),
    ],
  },
  {
    id: "compost",
    title: "Compost bin repairs",
    transcript:
      "The left bin has a cracked front board that lets the heat out. We have spare pallets behind the shed that would work as new sides. Rats were seen near the right bin last week.",
    segments: [
      user("cb-1", "Left bin: cracked board"),
      generated(
        "cb-2",
        "Cracked front board lets the heat out",
        "cb-1",
        "The left bin has a cracked front board that lets the heat out."
      ),
      user("cb-3", "Pallets behind shed"),
      generated("cb-4", "Rats near the right bin", "cb-3"),
      user("cb-5", "Who has a drill?"),
      user("cb-6", "Screws, not nails"),
      generated(
        "cb-7",
        "Spare pallets could work as new sides",
        "cb-3",
        "We have spare pallets behind the shed that would work as new sides."
      ),
    ],
  },
  {
    id: "watering-rota",
    title:
      "Watering rota for August, covering the east beds, the herb spiral and the two raised beds by the gate, with backups for holiday weeks",
    transcript:
      "East beds need watering every second morning, and the herb spiral every day when it is hot. The raised beds by the gate dry out fastest, so they go on the early list. Anyone away in the second week of August should find a swap before the rota is printed. The water butt is usually empty by Wednesday and refills only when it rains.",
    segments: [
      user("wr-1", "August rota", "heading"),
      user("wr-2", "East beds: every 2nd morning"),
      user("wr-3", "Herb spiral: daily in heat"),
      generated(
        "wr-4",
        "Herb spiral needs water every day when it is hot",
        "wr-3",
        "East beds need watering every second morning, and the herb spiral every day when it is hot."
      ),
      user("wr-5", "Gate beds first"),
      generated(
        "wr-6",
        "Raised beds by the gate dry out fastest, so they go first",
        "wr-5",
        "The raised beds by the gate dry out fastest, so they go on the early list.",
        "Why the gate beds are on the early list."
      ),
      user("wr-7", "Holiday week 2 - swaps"),
      generated(
        "wr-8",
        "Find a swap before the rota is printed",
        "wr-7",
        "Anyone away in the second week of August should find a swap before the rota is printed."
      ),
      user("wr-9", "Water butt empty by Wed"),
    ],
  },
  {
    id: "seed-swap",
    title: "Seed swap table",
    transcript:
      "The swap table will be by the gate from ten. Please label every packet with the variety and the year. Leftover seeds go to the school garden club.",
    segments: [],
  },
]

function sentences(text: string): string[] {
  return text.match(/[^.!?]+[.!?]/g)?.map((sentence) => sentence.trim()) ?? []
}

function wait(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) return reject(new DOMException("Aborted", "AbortError"))
    const timer = setTimeout(resolve, ms)
    signal.addEventListener(
      "abort",
      () => {
        clearTimeout(timer)
        reject(new DOMException("Aborted", "AbortError"))
      },
      { once: true }
    )
  })
}

async function generateFromTranscript(
  note: GardenNote,
  signal: AbortSignal
): Promise<NoteSegment[]> {
  await wait(1200, signal)
  const anchors = note.segments.filter(
    (segment) => segment.origin === "user" && segment.text.trim()
  )
  const generation = crypto.randomUUID()
  return sentences(note.transcript)
    .slice(0, 5)
    .map((sentence, index) => ({
      id: `${note.id}-gen-${generation}-${index}`,
      origin: "generated" as const,
      text: sentence,
      kind: "bullet" as const,
      after:
        anchors.length > 0 ? anchors[index % anchors.length].id : undefined,
      source: {
        excerpt: sentence,
        label: "Transcript",
        summary: "Drafted from this sentence of the transcript.",
      },
    }))
}

const newGardenNote = (): GardenNote => ({
  id: crypto.randomUUID(),
  title: "Untitled note",
  segments: [],
  transcript:
    "Beds one and two are ready for compost. The delivery arrives on Friday morning. Someone needs to unlock the side gate.",
})

type Preview = "live" | "empty" | "loading" | "error"

export default function Demo() {
  const [preview, setPreview] = useState<Preview>("live")

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex shrink-0 items-center gap-2 border-b px-3 py-2 text-xs text-muted-foreground">
        <span id="assisted-notes-preview-label">Preview state</span>
        <ToggleGroup
          type="single"
          variant="outline"
          size="sm"
          spacing={0}
          value={preview}
          aria-labelledby="assisted-notes-preview-label"
          onValueChange={(value) => {
            if (value) setPreview(value as Preview)
          }}
        >
          {(["live", "empty", "loading", "error"] as const).map((state) => (
            <ToggleGroupItem key={state} value={state}>
              {state}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      </div>
      <div className="min-h-0 flex-1">
        {preview === "live" ? (
          <AssistedNotes<GardenNote>
            collection="assisted-notes-demo"
            seed={seed}
            onGenerate={generateFromTranscript}
            newNote={newGardenNote}
          />
        ) : preview === "empty" ? (
          <EmptyState
            title="No notes yet"
            description="Write your own lines, then generate more from them."
            action={
              <Button onClick={() => setPreview("live")}>New note</Button>
            }
          />
        ) : preview === "loading" ? (
          <LoadingState label="Loading notes" />
        ) : (
          <ErrorState
            error={new Error("Could not read the notes from this browser.")}
            onRetry={() => setPreview("live")}
          />
        )}
      </div>
    </div>
  )
}
