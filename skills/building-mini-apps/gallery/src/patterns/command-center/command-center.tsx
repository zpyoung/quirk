import { useEffect, useRef, useState } from "react"
import {
  ChevronDownIcon,
  ChevronRightIcon,
  PauseIcon,
  RadioIcon,
  TriangleAlertIcon,
  WifiOffIcon,
} from "lucide-react"
import { toast } from "sonner"

import { EmptyState, ErrorState, LoadingState } from "@/components/mini/states"
import { Button } from "@/components/ui/button"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"

import { itemStatus } from "./attention"
import { AttentionQueue } from "./attention-queue"
import { BadgeRow } from "./badge-row"
import { clock } from "./format"
import { TileBoard } from "./tile-board"
import { TileDialog } from "./tile-dialog"
import { activeItemFor } from "./tile-shared"
import type { RefreshState, Summary, Tile } from "./types"
import { useCommandCenter } from "./use-command-center"

const NARROW_PX = 768

export type CommandCenterProps = Parameters<typeof useCommandCenter>[0] & {
  sourceLabel: string
  loadedAt?: number
  summaries?: Summary[]
  status?: "loading" | "ready" | "error"
  error?: Error
  onRetry?: () => void
}

function useNarrow(ref: React.RefObject<HTMLElement | null>): boolean {
  const [narrow, setNarrow] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const observer = new ResizeObserver(([entry]) =>
      setNarrow(entry.contentRect.width < NARROW_PX)
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [ref])
  return narrow
}

function RefreshStatus({
  refresh,
  onPause,
  onResume,
}: {
  refresh: RefreshState
  onPause(): void
  onResume(): void
}) {
  if (refresh.state === "none") return null
  const pause = (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          size="icon-xs"
          variant="ghost"
          aria-label="Pause refreshing"
          onClick={onPause}
        >
          <PauseIcon aria-hidden />
        </Button>
      </TooltipTrigger>
      <TooltipContent>Pause refreshing</TooltipContent>
    </Tooltip>
  )
  if (refresh.state === "paused") {
    return (
      <span className="flex items-center gap-1.5">
        <PauseIcon aria-hidden className="size-3" />
        Paused
        <Button size="xs" variant="outline" onClick={onResume}>
          Resume
        </Button>
      </span>
    )
  }
  if (refresh.state === "stale") {
    return (
      <span className="flex items-center gap-1.5">
        <WifiOffIcon aria-hidden className="size-3" />
        {refresh.since ? `Stale since ${clock(refresh.since)}` : "Stale"}
        {pause}
      </span>
    )
  }
  return (
    <span className="flex items-center gap-1.5">
      <RadioIcon aria-hidden className="size-3" />
      Live · updated {clock(refresh.at)}
      {pause}
    </span>
  )
}

/**
 * Status tiles in sections beside a queue of items that need the user. Wire it
 * to storage with `onTileUpdate`, `onItemAdd` and `onItemUpdate`; flag rules turn
 * tile conditions into queue items. Renders no AppShell, Toaster or TooltipProvider.
 */
export function CommandCenter(props: CommandCenterProps) {
  const {
    tiles,
    items,
    sourceLabel,
    loadedAt,
    summaries = [],
    status = "ready",
    error,
    onRetry,
    onTileUpdate,
  } = props
  const { now, announcement, refresh, pause, resume, retry, act } =
    useCommandCenter(props)

  const rootRef = useRef<HTMLDivElement>(null)
  const queueRef = useRef<HTMLDivElement>(null)
  const returnFocusRef = useRef<HTMLElement | null>(null)
  const narrow = useNarrow(rootRef)
  const [stripOpen, setStripOpen] = useState(false)
  const [openTileId, setOpenTileId] = useState<string | null>(null)

  const needYou = items.filter((item) => {
    const s = itemStatus(item, now)
    return s === "open" || s === "acknowledged"
  })
  const openTile = tiles.find((tile) => tile.id === openTileId) ?? null
  const linkedItem = openTile
    ? (activeItemFor(items, openTile.id, now) ??
      items
        .filter((item) => item.tileId === openTile.id)
        .sort(
          (a, b) => (b.timeline[0]?.at ?? 0) - (a.timeline[0]?.at ?? 0)
        )[0] ??
      null)
    : null

  const write = (what: string, id: string, patch: Partial<Tile>) => {
    onTileUpdate(id, { ...patch, updatedAt: Date.now() }).catch(
      (cause: unknown) =>
        toast.error(`Couldn't ${what}`, {
          description: cause instanceof Error ? cause.message : String(cause),
        })
    )
  }
  const toggle = (tile: Tile) =>
    write(`change ${tile.name}`, tile.id, { on: !tile.on })

  const showTile = (id: string, trigger?: HTMLElement | null) => {
    returnFocusRef.current =
      trigger ?? (document.activeElement as HTMLElement | null)
    setOpenTileId(id)
  }

  const focusQueue = () => {
    setStripOpen(true)
    requestAnimationFrame(() => {
      const row =
        queueRef.current?.querySelector<HTMLElement>("[data-queue-row]")
      const root =
        queueRef.current?.querySelector<HTMLElement>("[data-queue-root]")
      ;(row ?? root)?.focus()
    })
  }

  const ready = status === "ready"
  const queueLabel =
    needYou.length > 0 ? `${needYou.length} need you` : "Nothing needs you"

  let tileArea
  if (status === "loading") tileArea = <LoadingState label="Loading tiles" />
  else if (status === "error") {
    tileArea = (
      <ErrorState
        error={error ?? new Error("Could not load tiles")}
        onRetry={onRetry}
      />
    )
  } else if (tiles.length === 0) {
    tileArea = (
      <EmptyState
        title="No tiles yet"
        description="Tiles you add show up here."
      />
    )
  } else {
    tileArea = (
      <TileBoard
        tiles={tiles}
        items={items}
        now={now}
        onToggle={toggle}
        onOpen={(tile, trigger) => showTile(tile.id, trigger)}
        onLevel={(tile, value) => write(`set ${tile.name}`, tile.id, { value })}
        onTarget={(tile, target) =>
          write(`set ${tile.name}`, tile.id, { target })
        }
      />
    )
  }

  return (
    <div ref={rootRef} className="@container flex h-full min-h-0 flex-col">
      <header className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b px-3 py-2 text-xs text-muted-foreground">
        <span className="font-medium text-foreground">
          {sourceLabel}
          {loadedAt ? ` · loaded ${clock(loadedAt)}` : ""}
        </span>
        <RefreshStatus refresh={refresh} onPause={pause} onResume={resume} />
      </header>

      {refresh.state === "stale" ? (
        <div
          role="alert"
          className="mx-3 mt-3 flex flex-wrap items-center gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive"
        >
          <TriangleAlertIcon aria-hidden className="size-3.5" />
          <span className="flex-1">
            Couldn't refresh: {refresh.error.message}
          </span>
          <Button size="xs" variant="outline" onClick={retry}>
            Retry
          </Button>
        </div>
      ) : null}

      {ready ? (
        <div className="px-3 pt-3">
          <BadgeRow
            summaries={summaries}
            needYouCount={needYou.length}
            onFocusQueue={focusQueue}
            onOpenTile={(id) => showTile(id)}
          />
        </div>
      ) : null}

      <div className="flex min-h-0 flex-1 flex-col @min-[768px]:flex-row">
        {ready ? (
          <Collapsible
            ref={queueRef}
            open={narrow ? stripOpen : true}
            onOpenChange={setStripOpen}
            className="mt-3 border-y @min-[768px]:order-last @min-[768px]:mt-0 @min-[768px]:flex @min-[768px]:w-80 @min-[768px]:shrink-0 @min-[768px]:flex-col @min-[768px]:border-t-0 @min-[768px]:border-b-0 @min-[768px]:border-l"
          >
            <CollapsibleTrigger className="flex w-full items-center gap-1.5 px-3 py-2 text-left text-sm font-medium outline-none focus-visible:ring-3 focus-visible:ring-ring/50 @min-[768px]:hidden">
              {stripOpen ? (
                <ChevronDownIcon aria-hidden className="size-4" />
              ) : (
                <ChevronRightIcon aria-hidden className="size-4" />
              )}
              {queueLabel}
            </CollapsibleTrigger>
            <h2 className="hidden px-3 py-2 text-xs font-medium tracking-wide text-muted-foreground uppercase @min-[768px]:block">
              Needs you
            </h2>
            <CollapsibleContent className="h-64 @min-[768px]:h-auto @min-[768px]:min-h-0 @min-[768px]:flex-1">
              <AttentionQueue
                items={items}
                tiles={tiles}
                now={now}
                onAct={act}
                onOpenTile={(id) => showTile(id)}
              />
            </CollapsibleContent>
          </Collapsible>
        ) : null}
        <div className="min-h-0 flex-1 overflow-auto p-3">{tileArea}</div>
      </div>

      <TileDialog
        tile={openTile}
        item={linkedItem}
        now={now}
        returnFocusRef={returnFocusRef}
        onOpenChange={(open) => {
          if (!open) setOpenTileId(null)
        }}
        onToggle={toggle}
        onAct={(action) => linkedItem && act(linkedItem.id, action)}
      />

      <div role="status" aria-live="polite" className="sr-only">
        {announcement}
      </div>
    </div>
  )
}
