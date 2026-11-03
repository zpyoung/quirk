import { useState } from "react"
import {
  ClockAlertIcon,
  MinusIcon,
  PlusIcon,
  TriangleAlertIcon,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

import { isStale, itemStatus, stateText } from "./attention"
import { useToggleConfirm } from "./confirm-dialog"
import { ageText } from "./format"
import { Sparkline } from "./sparkline"
import { KindIcon, activeItemFor, hasNumericHistory } from "./tile-shared"
import type { AttentionItem, Tile } from "./types"

const TARGET_STEP = 0.5

function LevelSlider({
  tile,
  onLevel,
}: {
  tile: Tile
  onLevel(tile: Tile, value: number): void
}) {
  const [draft, setDraft] = useState<number | null>(null)
  const commit = () => {
    if (draft === null) return
    onLevel(tile, draft)
    setDraft(null)
  }
  return (
    <input
      type="range"
      min={0}
      max={100}
      value={draft ?? tile.value ?? 0}
      aria-label={`${tile.name} level`}
      onChange={(e) => setDraft(Number(e.target.value))}
      onPointerUp={commit}
      onKeyUp={commit}
      onBlur={commit}
      className="mx-2 mb-2 accent-(--mini-accent)"
    />
  )
}

function TargetStepper({
  tile,
  onTarget,
}: {
  tile: Tile
  onTarget(tile: Tile, target: number): void
}) {
  const target = tile.target ?? 0
  return (
    <div className="mx-2 mb-2 flex items-center gap-1">
      <Button
        size="icon-xs"
        variant="outline"
        aria-label={`Lower ${tile.name} target`}
        onClick={() => onTarget(tile, target - TARGET_STEP)}
      >
        <MinusIcon aria-hidden />
      </Button>
      <span className="min-w-12 text-center text-xs tabular-nums">
        {target}
        {tile.unit}
      </span>
      <Button
        size="icon-xs"
        variant="outline"
        aria-label={`Raise ${tile.name} target`}
        onClick={() => onTarget(tile, target + TARGET_STEP)}
      >
        <PlusIcon aria-hidden />
      </Button>
    </div>
  )
}

function TileCard({
  tile,
  item,
  now,
  onToggle,
  onOpen,
  onLevel,
  onTarget,
}: {
  tile: Tile
  item: AttentionItem | undefined
  now: number
  onToggle(tile: Tile, trigger: HTMLElement): void
  onOpen(tile: Tile, trigger: HTMLElement): void
  onLevel(tile: Tile, value: number): void
  onTarget(tile: Tile, target: number): void
}) {
  const stale = isStale(tile, now)
  return (
    <div
      data-tile-id={tile.id}
      data-attention={item ? "true" : undefined}
      data-stale={stale ? "true" : undefined}
      className={cn(
        "flex flex-col rounded-lg border bg-card text-card-foreground",
        item && "border-(--mini-accent) bg-(--mini-pending)"
      )}
    >
      <div className="flex items-start gap-1.5 p-2">
        {tile.kind !== "sensor" ? (
          <button
            type="button"
            aria-label={`Toggle ${tile.name}`}
            aria-pressed={!!tile.on}
            onClick={(e) => onToggle(tile, e.currentTarget)}
            className={cn(
              "flex size-8 shrink-0 items-center justify-center rounded-md border outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
              tile.on
                ? "border-transparent bg-(--mini-accent-soft) text-(--mini-accent)"
                : "bg-background text-muted-foreground hover:bg-muted"
            )}
          >
            <KindIcon kind={tile.kind} className="size-4" />
          </button>
        ) : (
          <span className="flex size-8 shrink-0 items-center justify-center text-muted-foreground">
            <KindIcon kind={tile.kind} className="size-4" />
          </span>
        )}
        <button
          type="button"
          onClick={(e) => onOpen(tile, e.currentTarget)}
          className="flex min-w-0 flex-1 flex-col gap-0.5 rounded-md text-left outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
        >
          <span className="truncate text-xs text-muted-foreground">
            {tile.name}
          </span>
          <span className={cn("text-sm font-semibold", stale && "opacity-50")}>
            {stateText(tile)}
          </span>
          {item ? (
            <span className="flex items-center gap-1 text-xs font-medium">
              <TriangleAlertIcon aria-hidden className="size-3" />
              {itemStatus(item, now) === "acknowledged"
                ? "Acknowledged"
                : "Needs you"}
            </span>
          ) : null}
          {stale ? (
            <span className="flex items-center gap-1 text-xs text-muted-foreground">
              <ClockAlertIcon aria-hidden className="size-3" />
              Stale · Updated {ageText(now - tile.updatedAt)} ago
            </span>
          ) : null}
          {hasNumericHistory(tile) ? (
            <Sparkline
              values={tile.history}
              className={cn("mt-1", stale && "opacity-50")}
            />
          ) : null}
        </button>
      </div>
      {tile.kind === "level" && tile.on ? (
        <LevelSlider tile={tile} onLevel={onLevel} />
      ) : null}
      {tile.kind === "target" ? (
        <TargetStepper tile={tile} onTarget={onTarget} />
      ) : null}
    </div>
  )
}

/** Tiles grouped into sections in order of first appearance; the icon toggles, the body opens details. */
export function TileBoard({
  tiles,
  items,
  now,
  onToggle,
  onOpen,
  onLevel,
  onTarget,
}: {
  tiles: Tile[]
  items: AttentionItem[]
  now: number
  onToggle(tile: Tile): void
  onOpen(tile: Tile, trigger: HTMLElement): void
  onLevel(tile: Tile, value: number): void
  onTarget(tile: Tile, target: number): void
}) {
  const confirm = useToggleConfirm(onToggle)
  const sections = [...new Set(tiles.map((tile) => tile.section))]

  return (
    <div className="flex flex-col gap-4">
      {sections.map((section, i) => (
        <section key={section} aria-labelledby={`tile-section-${i}`}>
          <h2
            id={`tile-section-${i}`}
            className="mb-1.5 text-xs font-medium tracking-wide text-muted-foreground uppercase"
          >
            {section}
          </h2>
          <div className="grid grid-cols-1 gap-2 @min-[768px]:grid-cols-[repeat(auto-fill,minmax(11rem,1fr))]">
            {tiles
              .filter((tile) => tile.section === section)
              .map((tile) => (
                <TileCard
                  key={tile.id}
                  tile={tile}
                  item={activeItemFor(items, tile.id, now)}
                  now={now}
                  onToggle={confirm.request}
                  onOpen={onOpen}
                  onLevel={onLevel}
                  onTarget={onTarget}
                />
              ))}
          </div>
        </section>
      ))}
      {confirm.dialog}
    </div>
  )
}
