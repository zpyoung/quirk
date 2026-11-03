import { useMemo, useRef, type ReactNode } from "react"
import { useHotkeys } from "react-hotkeys-hook"

import { EmptyState, ErrorState, LoadingState } from "@/components/mini/states"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { cn } from "@/lib/utils"

import { ControlBar } from "./control-bar"
import {
  countByKind,
  cursorAt,
  formatClock,
  isPlayable,
  markerPositions,
  nextEventTime,
  snapshotAt,
  sortByTime,
} from "./playback"
import { TimedList } from "./timed-list"
import type { ReplayRecording, ReplaySnapshot, ReplayTab } from "./types"
import { usePlayback } from "./use-playback"
import { UrlBar, Viewport } from "./viewport"

export type ReplayPlayerProps<S> = {
  items: ReplayRecording<S>[]
  status?: "loading" | "ready" | "error"
  error?: Error
  onRetry?: () => void
  renderSnapshot: (snapshot: ReplaySnapshot<S>) => ReactNode
  activeId?: string
  extraTabs?: ReplayTab[]
  emptyTitle?: string
  "aria-label"?: string
}

const BUILT_IN_TABS: ReplayTab[] = [
  {
    id: "activity",
    label: "Activity",
    kinds: ["click", "navigation", "error"],
    emptyTitle: "No activity in this replay",
  },
  {
    id: "console",
    label: "Console",
    kinds: ["console"],
    emptyTitle: "No console messages",
  },
  {
    id: "network",
    label: "Network",
    kinds: ["network"],
    emptyTitle: "No requests in this replay",
  },
  {
    id: "errors",
    label: "Errors",
    kinds: ["error"],
    emptyTitle: "No errors in this replay",
    emptyDescription: "Nothing failed while this was recorded.",
  },
]

/**
 * Plays back a recording of snapshots with transport controls, a marker lane,
 * and tabs of timed lists that follow the playhead and seek on click.
 * Takes `items` and `status` as props and never reads the store.
 */
export function ReplayPlayer<S>({
  items,
  status = "ready",
  error,
  onRetry,
  renderSnapshot,
  activeId,
  extraTabs = [],
  emptyTitle = "No replay to show",
  "aria-label": ariaLabel = "Replay player",
}: ReplayPlayerProps<S>) {
  const recording = items.find((item) => item.id === activeId) ?? items[0]
  let body: ReactNode
  if (status === "loading") {
    body = <LoadingState label="Loading replay" />
  } else if (status === "error") {
    body = (
      <ErrorState
        error={error ?? new Error("The replay could not be loaded.")}
        onRetry={onRetry}
      />
    )
  } else if (!recording || !isPlayable(recording)) {
    body = <EmptyState title={emptyTitle} />
  } else {
    body = (
      <Player
        key={recording.id}
        recording={recording}
        renderSnapshot={renderSnapshot}
        tabs={[...BUILT_IN_TABS, ...extraTabs]}
        ariaLabel={ariaLabel}
      />
    )
  }
  return (
    <div className="@container flex h-full min-h-[34rem] flex-col">
      {body}
    </div>
  )
}

function Player<S>({
  recording,
  renderSnapshot,
  tabs,
  ariaLabel,
}: {
  recording: ReplayRecording<S>
  renderSnapshot: (snapshot: ReplaySnapshot<S>) => ReactNode
  tabs: ReplayTab[]
  ariaLabel: string
}) {
  const { durationMs } = recording
  const rootRef = useRef<HTMLDivElement>(null)
  const playback = usePlayback(durationMs)
  const { time } = playback

  const events = useMemo(
    () =>
      sortByTime(recording.events).map((event) => ({
        ...event,
        at: Math.min(Math.max(event.at, 0), durationMs),
      })),
    [recording.events, durationMs]
  )
  const snapshots = useMemo(() => sortByTime(recording.snapshots), [recording.snapshots])
  const markers = useMemo(() => markerPositions(events, durationMs), [events, durationMs])
  const byTab = useMemo(
    () =>
      tabs.map((tab) => ({
        tab,
        entries: events.filter((event) => tab.kinds.includes(event.kind)),
      })),
    [tabs, events]
  )

  const snapshot = snapshotAt(snapshots, time)
  const cursor = cursorAt(events, time)
  const clicks = countByKind(events, "click")
  const errors = countByKind(events, "error")

  const inScope = (event: KeyboardEvent) => {
    const target = event.target
    if (target === document.body || target === document.documentElement) return true
    return target instanceof Node && rootRef.current?.contains(target) === true
  }
  const onTab = (event: KeyboardEvent) =>
    event.target instanceof Element && event.target.closest('[role="tab"]') !== null
  // Space on these activates them natively; the slider handles its own arrows
  const nativeSpace = (event: KeyboardEvent) =>
    event.target instanceof Element &&
    event.target.closest('button, a, [role="tab"]') !== null
  const onSlider = (event: KeyboardEvent) =>
    event.target instanceof Element && event.target.closest('[role="slider"]') !== null

  useHotkeys("space", (event) => {
    if (!inScope(event) || nativeSpace(event)) return
    event.preventDefault()
    if (event.repeat) return
    playback.toggle()
  })
  useHotkeys("left", (event) => {
    if (!inScope(event) || onTab(event) || onSlider(event)) return
    event.preventDefault()
    playback.skip(-5000)
  })
  useHotkeys("right", (event) => {
    if (!inScope(event) || onTab(event) || onSlider(event)) return
    event.preventDefault()
    playback.skip(5000)
  })

  return (
    <div
      ref={rootRef}
      role="region"
      aria-label={ariaLabel}
      className="flex min-h-0 flex-1 flex-col"
    >
      <span role="status" className="sr-only">
        {playback.playing ? "Playing" : "Paused"}
      </span>
      <header className="flex shrink-0 items-center gap-3 border-b px-3 py-2">
        <span
          aria-hidden
          className="flex size-8 shrink-0 items-center justify-center rounded-full bg-muted text-sm font-medium uppercase"
        >
          {recording.user.slice(0, 1)}
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium">{recording.user}</p>
          <p className="truncate text-xs text-muted-foreground">
            {[recording.meta, recording.whenLabel, formatClock(durationMs)]
              .filter(Boolean)
              .join(" · ")}
          </p>
        </div>
        <dl className="flex shrink-0 gap-4 text-right">
          <div>
            <dt className="text-xs text-muted-foreground">Clicks</dt>
            <dd className="text-sm font-medium tabular-nums">{clicks}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Errors</dt>
            <dd
              className={cn(
                "text-sm font-medium tabular-nums",
                errors > 0 && "text-destructive"
              )}
            >
              {errors}
            </dd>
          </div>
        </dl>
      </header>
      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto @3xl:flex-row @3xl:overflow-hidden">
        <section
          tabIndex={0}
          aria-label="Player"
          className="flex min-h-[30rem] min-w-0 shrink-0 flex-col gap-2 p-3 @3xl:min-h-0 outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset @3xl:basis-[42%]"
        >
          <UrlBar url={snapshot?.url ?? ""} />
          <Viewport time={formatClock(time)} url={snapshot?.url ?? ""} cursor={cursor}>
            {snapshot ? renderSnapshot(snapshot) : null}
          </Viewport>
          <ControlBar
            time={time}
            durationMs={durationMs}
            playing={playback.playing}
            ended={playback.ended}
            speed={playback.speed}
            markers={markers}
            onToggle={playback.toggle}
            onBack={() => playback.skip(-10_000)}
            onSkip={() => playback.seek(nextEventTime(events, time, durationMs))}
            onSeek={playback.seek}
            onStepSpeed={playback.changeSpeed}
          />
        </section>
        <Tabs
          defaultValue={tabs[0]?.id}
          className="min-h-[18rem] min-w-0 flex-1 gap-0 border-t pt-2 @3xl:border-t-0 @3xl:border-l"
        >
          <TabsList
            variant="line"
            className="h-auto w-full shrink-0 flex-wrap justify-start px-2"
          >
            {tabs.map((tab) => (
              <TabsTrigger key={tab.id} value={tab.id} className="flex-none px-2">
                {tab.label}
              </TabsTrigger>
            ))}
          </TabsList>
          {byTab.map(({ tab, entries }) => (
            <TabsContent
              key={tab.id}
              value={tab.id}
              className="mt-2 flex min-h-0 flex-1 flex-col"
            >
              <TimedList
                entries={entries}
                time={time}
                onSeek={playback.seek}
                label={tab.label}
                emptyTitle={tab.emptyTitle}
                emptyDescription={tab.emptyDescription}
              />
            </TabsContent>
          ))}
        </Tabs>
      </div>
    </div>
  )
}
