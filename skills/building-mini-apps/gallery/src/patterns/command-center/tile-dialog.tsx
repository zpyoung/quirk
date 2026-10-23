import { useState, type RefObject } from "react"
import { ClockAlertIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

import { isStale, itemStatus, stateText } from "./attention"
import { useToggleConfirm } from "./confirm-dialog"
import { exactTime } from "./format"
import { ItemDetail, StatusLabel } from "./item-detail"
import { Sparkline } from "./sparkline"
import { hasNumericHistory, toggleVerb } from "./tile-shared"
import type { AttentionItem, ItemAction, Tile } from "./types"

function historyLabel(tile: Tile & { history: number[] }): string {
  const unit = tile.unit ?? ""
  const latest = tile.history[tile.history.length - 1]
  return `${tile.name} history: latest ${latest}${unit}, min ${Math.min(...tile.history)}${unit}, max ${Math.max(...tile.history)}${unit}`
}

/**
 * Details for one tile: controls, exact last update, history chart and, when
 * the tile has an item, that item's actions and timeline. `tile` null closes it.
 */
export function TileDialog({
  tile,
  item,
  now,
  returnFocusRef,
  onOpenChange,
  onToggle,
  onAct,
}: {
  tile: Tile | null
  item: AttentionItem | null
  now: number
  returnFocusRef: RefObject<HTMLElement | null>
  onOpenChange(open: boolean): void
  onToggle(tile: Tile): void
  onAct(action: ItemAction): void
}) {
  // keeps the last tile on screen while the dialog animates out
  const [lastTile, setLastTile] = useState(tile)
  const [lastItem, setLastItem] = useState(item)
  if (tile && tile !== lastTile) setLastTile(tile)
  if (tile && item !== lastItem) setLastItem(item)
  const shown = tile ?? lastTile
  const shownItem = tile ? item : lastItem
  const confirm = useToggleConfirm(onToggle)

  return (
    <>
      <Dialog open={tile !== null} onOpenChange={onOpenChange}>
        <DialogContent
          className="max-h-[85vh] overflow-y-auto sm:max-w-md"
          onCloseAutoFocus={(e) => {
            e.preventDefault()
            returnFocusRef.current?.focus()
          }}
        >
          {shown ? (
            <>
              <DialogHeader>
                <DialogTitle>{shown.name}</DialogTitle>
                <DialogDescription>{shown.section}</DialogDescription>
              </DialogHeader>
              <div className="flex items-center justify-between gap-3">
                <span className="text-lg font-semibold">
                  {stateText(shown)}
                </span>
                {shown.kind !== "sensor" ? (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={(e) => confirm.request(shown, e.currentTarget)}
                  >
                    {toggleVerb(shown)}
                  </Button>
                ) : null}
              </div>
              <p className="flex flex-wrap items-center gap-x-2 text-xs text-muted-foreground">
                <span>
                  Last updated{" "}
                  <time dateTime={new Date(shown.updatedAt).toISOString()}>
                    {exactTime(shown.updatedAt)}
                  </time>
                </span>
                {isStale(shown, now) ? (
                  <span className="inline-flex items-center gap-1">
                    <ClockAlertIcon aria-hidden className="size-3" />
                    Stale
                  </span>
                ) : null}
              </p>
              {hasNumericHistory(shown) ? (
                <Sparkline
                  values={shown.history}
                  label={historyLabel(shown)}
                  className="h-24"
                />
              ) : null}
              {shownItem ? (
                <section
                  aria-label="Linked item"
                  className="flex flex-col gap-2 border-t pt-3"
                >
                  <div className="flex flex-col gap-0.5">
                    <h3 className="text-sm font-medium">{shownItem.title}</h3>
                    <p className="text-xs text-muted-foreground">
                      <StatusLabel status={itemStatus(shownItem, now)} /> ·{" "}
                      {shownItem.urgency === "now" ? "Now" : "Later"}
                    </p>
                  </div>
                  <ItemDetail
                    item={shownItem}
                    tile={shown}
                    now={now}
                    onAct={onAct}
                  />
                </section>
              ) : null}
            </>
          ) : null}
        </DialogContent>
      </Dialog>
      {confirm.dialog}
    </>
  )
}
