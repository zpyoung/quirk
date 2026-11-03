import { useCallback, useState } from "react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { useCollection } from "@/lib/mini/store"

import { ConditionalStatus } from "./conditional-status"
import { bugStatusModel, taskStatusModel } from "./models"
import { compareReleases, initialStatus, nextStatus } from "./status"
import type { StatusEvent, StatusItem, StatusRecord, Transition } from "./types"

type DemoItem = StatusItem & { list: "bugs" | "tasks" }

const HOUR = 3_600_000
const DAY = 24 * HOUR
const COMMITS = ["a1b2c3d", "e4f5a6b", "c7d8e9f"]

const BUG_MODEL = bugStatusModel(["2.2.0", "2.3.0", "2.4.0"])
const TASK_MODEL = taskStatusModel()

function buildSeed(): DemoItem[] {
  const t = Date.now()
  const bug = (
    id: string,
    title: string,
    occurrences: number,
    users: number,
    events: StatusEvent[] = []
  ): DemoItem => {
    let status: StatusRecord = {
      ...initialStatus(BUG_MODEL, t - 2 * DAY, "2.4.0"),
      occurrences,
      users,
    }
    for (const event of events) {
      status = nextStatus(status, event, BUG_MODEL, t - HOUR).record
    }
    return { id, title, list: "bugs", status }
  }
  const task = (
    id: string,
    title: string,
    events: StatusEvent[] = []
  ): DemoItem => {
    let status = initialStatus(TASK_MODEL, t - DAY)
    for (const event of events) {
      status = nextStatus(status, event, TASK_MODEL, t - HOUR).record
    }
    return { id, title, list: "tasks", status }
  }
  return [
    bug("BUG-101", "Crash when saving a recipe with no title", 48, 12),
    bug("BUG-102", "Search ignores accented letters", 31, 9, [
      { type: "choose", kind: "resolve-next" },
    ]),
    bug("BUG-103", "Shopping list loses items after a sync", 22, 7, [
      { type: "choose", kind: "resolve-commit", value: "a1b2c3d" },
    ]),
    bug("BUG-104", "Photo upload stalls on slow networks", 70, 18, [
      { type: "choose", kind: "archive-occurs", value: 8 },
      { type: "occurrence", count: 3 },
    ]),
    bug("BUG-105", "Timer chime plays twice", 15, 4, [
      { type: "choose", kind: "archive-forever" },
    ]),
    bug("BUG-106", "Dark mode flashes white on launch", 26, 11, [
      { type: "choose", kind: "archive-for", value: 3 * HOUR },
    ]),
    task("TASK-1", "Renew the passport"),
    task("TASK-2", "Reply to the landlord about the lease", [
      { type: "choose", kind: "snooze-reply" },
    ]),
    task("TASK-3", "Book a dentist appointment", [
      { type: "choose", kind: "snooze-for", value: 2 * HOUR },
    ]),
    task("TASK-4", "Water the ferns", [{ type: "choose", kind: "done" }]),
    task("TASK-5", "Plan the vegetable garden"),
  ]
}

type Preview = "live" | "empty" | "loading" | "error"
const PREVIEWS: Preview[] = ["live", "empty", "loading", "error"]
const PREVIEW_ERROR = new Error("The sample list could not be read.")

function latestRelease(items: DemoItem[]): string {
  return items
    .flatMap((item) => (item.status.release ? [item.status.release] : []))
    .reduce((a, b) => (compareReleases(b, a) > 0 ? b : a), "2.4.0")
}

function bumpPatch(version: string): string {
  const parts = version.split(".")
  const patch = Number(parts[parts.length - 1]) + 1
  return [...parts.slice(0, -1), String(patch)].join(".")
}

export default function Demo() {
  const [initialSeed] = useState(buildSeed)
  const store = useCollection<DemoItem>("conditional-status-demo", initialSeed)
  const [preview, setPreview] = useState<Preview>("live")
  const [list, setList] = useState<"bugs" | "tasks">("bugs")
  const [highlightedId, setHighlightedId] = useState<string | null>(null)
  const [offset, setOffset] = useState(0)
  const clock = useCallback(() => Date.now() + offset, [offset])

  const model = list === "bugs" ? BUG_MODEL : TASK_MODEL
  const status = preview === "live" ? store.status : preview === "empty" ? "ready" : preview
  const listed = store.items.filter((item) => item.list === list)
  const items = preview === "empty" ? [] : listed
  const highlighted = listed.find((item) => item.id === highlightedId)
  const bugs = store.items.filter((item) => item.list === "bugs")
  const shipped = latestRelease(bugs)
  const nextRelease = bumpPatch(shipped)
  const nextCommit = COMMITS[(Number(nextRelease.split(".").pop()) - 1) % COMMITS.length]

  const write = (
    item: DemoItem,
    record: StatusRecord,
    transition: Transition | null
  ) => {
    store.update(item.id, { status: record }).catch((cause: unknown) => {
      toast.error("Couldn't save the change", {
        description: cause instanceof Error ? cause.message : String(cause),
      })
    })
    if (transition) {
      const label = (list === "bugs" ? BUG_MODEL : TASK_MODEL).states[record.state]?.label
      toast(`${item.title}: ${label ?? record.state}`, {
        description: transition.reason,
      })
    }
  }

  const run = (item: DemoItem, events: StatusEvent[]) => {
    const itemModel = item.list === "bugs" ? BUG_MODEL : TASK_MODEL
    let record = item.status
    let transition: Transition | null = null
    for (const event of events) {
      const result = nextStatus(record, event, itemModel, clock())
      record = result.record
      transition = result.transition ?? transition
    }
    if (record !== item.status) write(item, record, transition)
  }

  const reset = () => {
    setOffset(0)
    setHighlightedId(null)
    setPreview("live")
    store.replaceAll(buildSeed()).catch((cause: unknown) => {
      toast.error("Couldn't reset the sample data", {
        description: cause instanceof Error ? cause.message : String(cause),
      })
    })
  }

  const keyHints = model.groups
    .filter((group) => group.key)
    .map((group) => `${group.key} ${group.label}`)
    .join(", ")
  const hints = [
    "j/k move",
    "x or Space check",
    "Esc clear",
    keyHints,
    `Shift+${model.groups[0]?.key ?? "r"} opens a menu`,
  ]

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
              onClick={() => setPreview(name)}
              className="capitalize"
            >
              {name}
            </Button>
          ))}
        </div>
        <span className="ml-2 text-xs text-muted-foreground">Sample list</span>
        <div role="group" aria-label="Sample list" className="flex gap-1">
          {(["bugs", "tasks"] as const).map((name) => (
            <Button
              key={name}
              size="xs"
              variant={list === name ? "default" : "outline"}
              aria-pressed={list === name}
              onClick={() => {
                setList(name)
                setHighlightedId(null)
              }}
              className="capitalize"
            >
              {name}
            </Button>
          ))}
        </div>
        <Button size="xs" variant="ghost" onClick={reset}>
          Reset sample data
        </Button>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-muted-foreground">
          Events from the app (demo only)
        </span>
        {list === "bugs" ? (
          <>
            <Button
              size="xs"
              variant="outline"
              disabled={!highlighted}
              onClick={() =>
                highlighted &&
                run(highlighted, [{ type: "occurrence", release: shipped }])
              }
            >
              New event
            </Button>
            <Button
              size="xs"
              variant="outline"
              disabled={!highlighted}
              onClick={() =>
                highlighted &&
                run(highlighted, [
                  { type: "occurrence", release: shipped, newUsers: 1 },
                ])
              }
            >
              New event, new user
            </Button>
            <Button
              size="xs"
              variant="outline"
              disabled={!highlighted}
              onClick={() =>
                highlighted &&
                run(highlighted, [
                  { type: "occurrence", count: 60, release: shipped },
                  { type: "signal", name: "escalate" },
                ])
              }
            >
              Event spike
            </Button>
            <Button
              size="xs"
              variant="outline"
              onClick={() =>
                bugs.forEach((item) =>
                  run(item, [
                    {
                      type: "release",
                      version: nextRelease,
                      commits: [nextCommit],
                    },
                  ])
                )
              }
            >
              Ship {nextRelease}
            </Button>
          </>
        ) : (
          <Button
            size="xs"
            variant="outline"
            disabled={!highlighted}
            onClick={() =>
              highlighted && run(highlighted, [{ type: "signal", name: "reply" }])
            }
          >
            They reply
          </Button>
        )}
        <Button size="xs" variant="outline" onClick={() => setOffset((v) => v + DAY)}>
          Skip ahead one day
        </Button>
        <span className="text-xs text-muted-foreground">
          {list === "bugs"
            ? `Highlight a row first. ${nextRelease} will contain commit ${nextCommit}.`
            : "Highlight a row first."}
          {offset > 0 ? ` Clock is ${offset / DAY} day${offset === DAY ? "" : "s"} ahead.` : ""}
        </span>
      </div>

      <div className="min-h-[24rem] flex-1 overflow-hidden rounded-lg border">
        <ConditionalStatus
          key={list}
          aria-label={list === "bugs" ? "Bugs" : "Tasks"}
          items={items}
          model={model}
          status={status}
          error={PREVIEW_ERROR}
          onRetry={() => setPreview("live")}
          clock={clock}
          tickMs={2000}
          highlightedId={highlightedId}
          onHighlightedIdChange={setHighlightedId}
          renderLead={(item) => item.id}
          emptyTitle={list === "bugs" ? "No bugs" : "No tasks"}
          onChange={(id, record, transition) => {
            const item = store.items.find((candidate) => candidate.id === id)
            if (item) write(item, record, transition)
          }}
        />
      </div>

      <p className="text-xs text-muted-foreground">{hints.join(" · ")}</p>
    </div>
  )
}
