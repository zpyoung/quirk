import { useRef, useState } from "react"
import { ChevronDownIcon } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useCollection } from "@/lib/mini/store"

import { itemStatus, stateText } from "./attention"
import { CommandCenter } from "./command-center"
import type { AttentionItem, FlagRule, Tile } from "./types"

const MIN = 60_000
const HOUR = 3_600_000
const DAY = 24 * HOUR

function buildSeed(): { tiles: Tile[]; items: AttentionItem[] } {
  const t = Date.now()
  const tiles: Tile[] = [
    {
      id: "front-door",
      section: "Security",
      name: "Front door",
      kind: "toggle",
      on: true,
      onLabel: "Locked",
      offLabel: "Unlocked",
      onVerb: "Lock",
      offVerb: "Unlock",
      sensitive: true,
      updatedAt: t - 2 * MIN,
    },
    {
      id: "garage-door",
      section: "Security",
      name: "Garage door",
      kind: "toggle",
      on: true,
      onLabel: "Closed",
      offLabel: "Open",
      onVerb: "Close",
      offVerb: "Open",
      updatedAt: t - 10 * MIN,
    },
    {
      id: "living-temp",
      section: "Climate",
      name: "Living room",
      kind: "target",
      on: true,
      value: 20.5,
      target: 21,
      unit: "°",
      updatedAt: t - 3 * MIN,
      history: [19.5, 19.8, 20, 20.2, 20.3, 20.4, 20.5],
    },
    {
      id: "basement-humidity",
      section: "Climate",
      name: "Basement humidity",
      kind: "sensor",
      value: 58,
      unit: "%",
      updatedAt: t - 5 * MIN,
      history: [49, 50, 52, 53, 55, 57, 58],
    },
    {
      id: "garage-temp",
      section: "Climate",
      name: "Garage temperature",
      kind: "sensor",
      value: 4,
      unit: "°",
      updatedAt: t - 3 * HOUR,
      staleAfterMs: HOUR,
      history: [6, 5.5, 5, 4.5, 4],
    },
    {
      id: "freezer-door",
      section: "Climate",
      name: "Freezer door",
      kind: "sensor",
      text: "Closed",
      updatedAt: t - 30 * MIN,
    },
    {
      id: "living-lights",
      section: "Lights",
      name: "Living room lights",
      kind: "level",
      on: true,
      value: 60,
      unit: "%",
      offLabel: "Off",
      updatedAt: t - 40 * MIN,
    },
    {
      id: "porch-light",
      section: "Lights",
      name: "Porch light",
      kind: "toggle",
      on: false,
      updatedAt: t - HOUR,
    },
    {
      id: "nas-backup",
      section: "Home network",
      name: "NAS backup",
      kind: "sensor",
      text: "Failed",
      unit: " min",
      updatedAt: t - 20 * MIN,
      staleAfterMs: DAY,
      staleOpensItem: true,
      history: [38, 41, 39, 43, 47, 55, 61],
    },
    {
      id: "internet",
      section: "Home network",
      name: "Internet speed",
      kind: "sensor",
      value: 412,
      unit: " Mbps",
      updatedAt: t - MIN,
      history: [380, 405, 398, 420, 415, 400, 412],
    },
  ]
  const items: AttentionItem[] = [
    {
      v: 1,
      id: "item-nas",
      title: "NAS backup failed",
      urgency: "now",
      tileId: "nas-backup",
      ruleId: "nas-failed",
      timeline: [{ at: t - 20 * MIN, type: "opened" }],
    },
    {
      v: 1,
      id: "item-humidity",
      title: "Basement humidity above 55%",
      urgency: "later",
      tileId: "basement-humidity",
      ruleId: "humidity-high",
      timeline: [{ at: t - 45 * MIN, type: "opened" }],
    },
    {
      v: 1,
      id: "item-smoke",
      title: "Replace smoke alarm battery",
      urgency: "later",
      timeline: [
        { at: t - DAY, type: "opened" },
        { at: t - 20 * HOUR, type: "acknowledged" },
      ],
    },
    {
      v: 1,
      id: "item-registration",
      title: "Renew car registration",
      urgency: "later",
      timeline: [
        { at: t - 2 * DAY, type: "opened" },
        {
          at: t - 3 * MIN,
          type: "snoozed",
          until: t + 90_000,
          note: "Waiting for the renewal letter",
        },
      ],
    },
    {
      v: 1,
      id: "item-freezer-old",
      title: "Freezer door open",
      urgency: "now",
      tileId: "freezer-door",
      ruleId: "freezer-open",
      timeline: [
        { at: t - 50 * HOUR, type: "opened" },
        {
          at: t - 49 * HOUR,
          type: "cleared",
          text: "Cleared: Freezer door closed",
        },
      ],
    },
  ]
  return { tiles, items }
}

const RULES: FlagRule[] = [
  {
    id: "front-door-unlocked",
    tileId: "front-door",
    title: "Front door unlocked",
    urgency: "now",
    test: (tile) => !tile.on,
  },
  {
    id: "humidity-high",
    tileId: "basement-humidity",
    title: "Basement humidity above 55%",
    urgency: "later",
    test: (tile) => (tile.value ?? 0) > 55,
    occurrence: (tile) => String(Math.floor((tile.value ?? 0) / 5)),
  },
  {
    id: "nas-failed",
    tileId: "nas-backup",
    title: "NAS backup failed",
    urgency: "now",
    test: (tile) => tile.text === "Failed",
  },
  {
    id: "freezer-open",
    tileId: "freezer-door",
    title: "Freezer door open",
    urgency: "now",
    test: (tile) => tile.text === "Open",
  },
]

type Preview = "live" | "empty" | "loading" | "error"
const PREVIEWS: Preview[] = ["live", "empty", "loading", "error"]
const PREVIEW_ERROR = new Error("The sample home could not be read.")

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

function reportWrite(write: Promise<void>, action: string): void {
  write.catch((cause: unknown) => {
    toast.error(`Couldn't ${action}`, {
      description: cause instanceof Error ? cause.message : String(cause),
    })
  })
}

export default function Demo() {
  const [initialSeed] = useState(buildSeed)
  const tilesStore = useCollection<Tile>(
    "command-center-tiles",
    initialSeed.tiles
  )
  const itemsStore = useCollection<AttentionItem>(
    "command-center-items",
    initialSeed.items
  )
  const [preview, setPreview] = useState<Preview>("live")
  const [epoch, setEpoch] = useState(0)
  const [loadedAt] = useState(() => Date.now())
  const [refreshFails, setRefreshFails] = useState(false)
  const refreshFailsRef = useRef(false)

  const loading =
    tilesStore.status === "loading" || itemsStore.status === "loading"
  const failed = tilesStore.status === "error" || itemsStore.status === "error"
  const status =
    preview === "loading" || preview === "error"
      ? preview
      : failed
        ? "error"
        : loading
          ? "loading"
          : "ready"
  const shown = status === "ready" && preview === "live"
  const tiles = shown ? tilesStore.items : []
  const items = shown ? itemsStore.items : []

  const tile = (id: string) =>
    tilesStore.items.find((candidate) => candidate.id === id)
  const patchTile = (id: string, patch: Partial<Tile>) =>
    reportWrite(
      tilesStore.update(id, { updatedAt: Date.now(), ...patch }),
      "update the tile"
    )

  const events: Array<{ label: string; run(): void }> = [
    {
      label: "Front door unlocks",
      run: () => patchTile("front-door", { on: false }),
    },
    {
      label: "Front door locks",
      run: () => patchTile("front-door", { on: true }),
    },
    {
      label: "Basement humidity rises above 55%",
      run: () => {
        const current = tile("basement-humidity")
        const value =
          (current?.value ?? 0) > 55 ? (current?.value ?? 0) + 6 : 62
        patchTile("basement-humidity", {
          value,
          history: [...(current?.history ?? []), value].slice(-12),
        })
      },
    },
    {
      label: "Basement humidity falls",
      run: () => {
        const current = tile("basement-humidity")
        patchTile("basement-humidity", {
          value: 47,
          history: [...(current?.history ?? []), 47].slice(-12),
        })
      },
    },
    {
      label: "NAS backup fails",
      run: () => patchTile("nas-backup", { text: "Failed" }),
    },
    {
      label: "NAS backup succeeds",
      run: () => patchTile("nas-backup", { text: "Backed up" }),
    },
    {
      label: "NAS backup stops reporting",
      run: () => patchTile("nas-backup", { updatedAt: Date.now() - 25 * HOUR }),
    },
    {
      label: "Freezer door left open",
      run: () => patchTile("freezer-door", { text: "Open" }),
    },
    {
      label: "Freezer door closes",
      run: () => patchTile("freezer-door", { text: "Closed" }),
    },
    {
      label: "Add “Electric bill due Friday”",
      run: () => {
        const exists = itemsStore.items.some(
          (item) =>
            item.title === "Electric bill due Friday" &&
            itemStatus(item, Date.now()) !== "resolved"
        )
        if (exists) {
          toast("Electric bill due Friday is already in the queue")
          return
        }
        reportWrite(
          itemsStore.add({
            v: 1,
            id: crypto.randomUUID(),
            title: "Electric bill due Friday",
            urgency: "later",
            timeline: [{ at: Date.now(), type: "opened" }],
          }),
          "add the item"
        )
      },
    },
  ]

  const lightsOn = tilesStore.items.filter(
    (t) => t.section === "Lights" && t.on
  ).length
  const summaries = shown
    ? [
        ...(tile("front-door")
          ? [
              {
                id: "front-door",
                label: `Front door ${stateText(tile("front-door")!).toLowerCase()}`,
                tileId: "front-door",
              },
            ]
          : []),
        {
          id: "lights",
          label: lightsOn === 1 ? "1 light on" : `${lightsOn} lights on`,
        },
        ...(tile("living-temp")
          ? [
              {
                id: "living-temp",
                label: `Living room ${stateText(tile("living-temp")!).split(" ")[0]}`,
                tileId: "living-temp",
              },
            ]
          : []),
      ]
    : []

  const reset = async () => {
    // tiles are hidden while both stores are replaced so no rule evaluates against half-reset data
    const previous = { tiles: tilesStore.items, items: itemsStore.items }
    setPreview("loading")
    const seed = buildSeed()
    const [tilesWrite, itemsWrite] = await Promise.allSettled([
      tilesStore.replaceAll(seed.tiles),
      itemsStore.replaceAll(seed.items),
    ])
    const failure = [tilesWrite, itemsWrite].find(
      (outcome) => outcome.status === "rejected"
    )
    if (failure) {
      // put back whichever collection did get replaced so the two never disagree
      const rollbacks = await Promise.allSettled([
        tilesWrite.status === "fulfilled"
          ? tilesStore.replaceAll(previous.tiles)
          : undefined,
        itemsWrite.status === "fulfilled"
          ? itemsStore.replaceAll(previous.items)
          : undefined,
      ])
      const partial = rollbacks.some((outcome) => outcome.status === "rejected")
      const cause = failure.reason
      toast.error("Couldn't reset the sample data", {
        description: `${cause instanceof Error ? cause.message : String(cause)} ${
          partial
            ? "Some data may be partly reset; reload to check."
            : "Your data was left as it was."
        }`,
      })
    }
    setEpoch((n) => n + 1)
    setPreview("live")
  }

  return (
    <div className="flex h-full min-h-[34rem] flex-col">
      <div className="flex shrink-0 flex-wrap items-center gap-2 border-b px-3 py-1.5">
        <span
          id="command-center-demo-preview"
          className="text-xs text-muted-foreground"
        >
          Preview state
        </span>
        <div
          role="group"
          aria-labelledby="command-center-demo-preview"
          className="flex gap-1"
        >
          {PREVIEWS.map((option) => (
            <Button
              key={option}
              size="xs"
              variant={preview === option ? "secondary" : "outline"}
              aria-pressed={preview === option}
              onClick={() => setPreview(option)}
              className="capitalize"
            >
              {option}
            </Button>
          ))}
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button size="xs" variant="outline" className="ml-auto">
              Simulate event
              <ChevronDownIcon aria-hidden />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel>Sample home</DropdownMenuLabel>
            {events.map((event) => (
              <DropdownMenuItem key={event.label} onSelect={event.run}>
                {event.label}
              </DropdownMenuItem>
            ))}
            <DropdownMenuSeparator />
            <DropdownMenuCheckboxItem
              checked={refreshFails}
              onCheckedChange={(checked) => {
                refreshFailsRef.current = checked
                setRefreshFails(checked)
              }}
            >
              Refresh fails
            </DropdownMenuCheckboxItem>
          </DropdownMenuContent>
        </DropdownMenu>
        <Button size="xs" variant="ghost" onClick={() => void reset()}>
          Reset sample data
        </Button>
      </div>
      <div className="min-h-0 flex-1">
        <CommandCenter
          key={epoch}
          tiles={tiles}
          items={items}
          rules={RULES}
          sourceLabel="Sample data"
          loadedAt={loadedAt}
          summaries={summaries}
          status={status}
          error={
            preview === "error"
              ? PREVIEW_ERROR
              : (tilesStore.error ?? itemsStore.error)
          }
          onRetry={() => setPreview("live")}
          onTileUpdate={tilesStore.update}
          onItemAdd={itemsStore.add}
          onItemUpdate={itemsStore.update}
          onRefresh={async (signal) => {
            await wait(400, signal)
            if (refreshFailsRef.current)
              throw new Error("The sample hub did not answer.")
            return []
          }}
          refreshMs={30_000}
        />
      </div>
    </div>
  )
}
