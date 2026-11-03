import {
  ActivityIcon,
  LightbulbIcon,
  PowerIcon,
  ThermometerIcon,
} from "lucide-react"

import { itemStatus } from "./attention"
import type { AttentionItem, Tile } from "./types"

export function KindIcon({
  kind,
  className,
}: {
  kind: Tile["kind"]
  className?: string
}) {
  const Icon =
    kind === "toggle"
      ? PowerIcon
      : kind === "level"
        ? LightbulbIcon
        : kind === "target"
          ? ThermometerIcon
          : ActivityIcon
  return <Icon className={className} aria-hidden />
}

/** The tile's item that still needs the user: open or acknowledged, Now before Later. */
export function activeItemFor(
  items: AttentionItem[],
  tileId: string,
  now: number
): AttentionItem | undefined {
  const active = items.filter((item) => {
    if (item.tileId !== tileId) return false
    const status = itemStatus(item, now)
    return status === "open" || status === "acknowledged"
  })
  return active.find((item) => item.urgency === "now") ?? active[0]
}

export function hasNumericHistory(
  tile: Tile
): tile is Tile & { history: number[] } {
  return tile.kind !== "toggle" && (tile.history?.length ?? 0) >= 2
}

export function toggleVerb(tile: Tile): string {
  return tile.on ? (tile.offVerb ?? "Turn off") : (tile.onVerb ?? "Turn on")
}
