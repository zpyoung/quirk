import { useEffect, useMemo, useState } from "react"
import {
  CloudOffIcon,
  HistoryIcon,
  MessageSquareIcon,
  PauseIcon,
  PencilLineIcon,
  PlayIcon,
  Share2Icon,
} from "lucide-react"

import { useCollection } from "@/lib/mini/store"
import { Button } from "@/components/ui/button"

import { EventTimeline } from "./event-timeline"
import type { TimelineEntry, TimelineType } from "./types"

type Preview = "live" | "empty" | "loading" | "error"

const PREVIEWS: Preview[] = ["live", "empty", "loading", "error"]

const TYPES: Record<string, TimelineType> = {
  edit: { label: "Edits", icon: PencilLineIcon, tone: 1 },
  comment: { label: "Comments", icon: MessageSquareIcon, tone: 2 },
  share: { label: "Sharing", icon: Share2Icon, tone: 3 },
  restore: { label: "Restores", icon: HistoryIcon, tone: 4 },
  sync: { label: "Sync", icon: CloudOffIcon, tone: 5 },
}

const DAY = Date.UTC(2026, 9, 19)
const at = (h: number, m: number, s: number) => DAY + ((h * 60 + m) * 60 + s) * 1000

const SEED: TimelineEntry[] = [
  { id: "ev-01", time: at(14, 2, 10), type: "edit", category: "Edit", level: "info", message: "Created the document from the trip template", detail: "Autumn trip itinerary" },
  { id: "ev-02", time: at(14, 6, 41), type: "edit", category: "Edit", level: "info", message: "Added the Day 1 schedule", detail: "Section: Day 1" },
  { id: "ev-03", time: at(14, 14, 3), type: "edit", category: "Edit", level: "info", message: "Pasted the train times for Day 2", detail: "Section: Day 2" },
  { id: "ev-04", time: at(14, 21, 37), type: "comment", category: "Comment", level: "info", message: "Joss: Is the 08:40 train too early for the group?", detail: "Thread on Day 2" },
  { id: "ev-05", time: at(14, 25, 12), type: "share", category: "Share", level: "info", message: "Shared with Joss as an editor" },
  { id: "ev-06", time: at(14, 33, 50), type: "edit", category: "Edit", level: "info", message: "Rewrote the packing list", detail: "Section: Packing" },
  { id: "ev-07", time: at(14, 41, 29), type: "sync", category: "Sync", level: "warning", message: "Autosave retried twice before it went through" },
  { id: "ev-08", time: at(14, 47, 5), type: "edit", category: "Edit", level: "info", message: "Moved the lunch stop from Day 2 to Day 3", detail: "Sections: Day 2, Day 3" },
  { id: "ev-09", time: at(14, 47, 5), type: "comment", category: "Comment", level: "info", message: "Mira: Moved. Day 2 now starts at 09:15.", detail: "Thread on Day 2" },
  { id: "ev-10", time: at(15, 1, 44), type: "edit", category: "Edit", level: "info", message: "Changed the hotel check-in time to 15:00", detail: "Section: Hotel" },
  { id: "ev-11", time: at(15, 9, 30), type: "restore", category: "Restore", level: "info", message: "Restored the 14:33 version of the packing list", detail: "Section: Packing" },
  { id: "ev-12", time: at(15, 12, 2), type: "edit", category: "Edit", level: "info", message: "Deleted the Spare ideas section" },
  { id: "ev-13", time: at(15, 18, 47), type: "edit", category: "Edit", level: "info", message: "Retyped the Day 3 route, including the long note about the harbour walk that nobody will read in full but that has to wrap onto several lines in a narrow window so the layout can be checked against it", detail: "Section: Day 3 / Route / Harbour walk" },
  { id: "ev-14", time: at(15, 21, 9), type: "sync", category: "Sync", level: "error", message: "Autosave could not reach the server", detail: "Edits after 15:18:47 are only on this device", isError: true },
  { id: "ev-15", time: at(15, 23, 20), type: "sync", category: "Sync", level: "info", message: "Back online, 1 pending edit saved" },
]

const timeFormat = new Intl.DateTimeFormat("en", {
  month: "short",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hourCycle: "h23",
  timeZone: "UTC",
})

const formatTime = (time: number) => timeFormat.format(time)

const HINTS = [
  "Click a time to seek",
  "/ search",
  "o switch order",
  "p jump to the playhead",
  "Esc clear search, then leave it",
  "Scroll the divider away and the list stops following",
]

export default function Demo() {
  const history = useCollection<TimelineEntry>("event-timeline-demo", SEED)
  const [preview, setPreview] = useState<Preview>("live")
  const [replay, setReplay] = useState(true)
  const [playhead, setPlayhead] = useState(at(15, 0, 0))
  const [playing, setPlaying] = useState(false)

  const times = useMemo(() => history.items.map((entry) => entry.time).sort((a, b) => a - b), [history.items])
  const first = times[0]
  const last = times.at(-1)
  const spanKnown = first !== undefined && last !== undefined && first < last
  const clamped = spanKnown ? Math.min(Math.max(playhead, first), last) : playhead
  const running = playing && spanKnown && clamped < last

  useEffect(() => {
    if (!running) return
    const id = window.setInterval(() => {
      setPlayhead((current) => times.find((time) => time > current) ?? current)
    }, 1000)
    return () => window.clearInterval(id)
  }, [running, times])

  const restoreSamples = () => {
    setPreview("live")
    void history.replaceAll(SEED)
  }

  const status = preview === "live" ? history.status : preview === "empty" ? "ready" : preview
  const entries = preview === "empty" ? [] : history.items

  const seek = (time: number) => {
    setPlaying(false)
    setPlayhead(time)
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 p-4">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <div className="flex items-center gap-2">
          <span className="text-xs whitespace-nowrap text-muted-foreground">State preview (demo only)</span>
          <div role="group" aria-label="State preview" className="flex gap-1">
            {PREVIEWS.map((name) => (
              <Button
                key={name}
                size="xs"
                variant={preview === name ? "default" : "outline"}
                aria-pressed={preview === name}
                onClick={() => setPreview(name)}
                className="capitalize"
              >
                {name}
              </Button>
            ))}
          </div>
        </div>
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <span className="text-xs whitespace-nowrap text-muted-foreground">Replay (demo only)</span>
          <Button
            size="xs"
            variant={replay ? "default" : "outline"}
            aria-pressed={replay}
            onClick={() => {
              setReplay(!replay)
              setPlaying(false)
            }}
          >
            Playhead {replay ? "on" : "off"}
          </Button>
          <Button
            size="icon-xs"
            variant="outline"
            disabled={!replay || !spanKnown}
            aria-label={running ? "Pause replay" : "Play replay"}
            onClick={() => {
              if (clamped >= (last ?? 0)) setPlayhead(first ?? playhead)
              setPlaying(!running)
            }}
          >
            {running ? <PauseIcon aria-hidden /> : <PlayIcon aria-hidden />}
          </Button>
          <input
            type="range"
            aria-label="Playhead position"
            disabled={!replay || !spanKnown}
            min={first ?? 0}
            max={last ?? 0}
            step={1000}
            value={clamped}
            onChange={(event) => seek(Number(event.target.value))}
            className="w-40 accent-primary"
          />
          <span className="text-xs whitespace-nowrap text-muted-foreground tabular-nums">
            {replay && spanKnown ? formatTime(clamped) : "off"}
          </span>
        </div>
      </div>

      <div className="min-h-[24rem] flex-1 overflow-hidden rounded-lg border">
        <EventTimeline
          aria-label="Document edit history"
          entries={entries}
          status={status}
          error={new Error("Could not read the edit history (simulated).")}
          onRetry={() => setPreview("live")}
          types={TYPES}
          playhead={replay && spanKnown ? clamped : undefined}
          onSeek={seek}
          formatTime={formatTime}
          errorLabel="Save failed"
          emptyTitle="No edits recorded yet"
          emptyAction={{ label: "Restore sample history", onClick: restoreSamples }}
        />
      </div>

      <p className="text-xs text-muted-foreground">{HINTS.join(" · ")}</p>
    </div>
  )
}
