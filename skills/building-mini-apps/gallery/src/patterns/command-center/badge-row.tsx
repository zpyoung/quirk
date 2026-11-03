import { Badge } from "@/components/ui/badge"

import type { Summary } from "./types"

/** Summary badges from the app plus one "N need you" count that focuses the queue. */
export function BadgeRow({
  summaries,
  needYouCount,
  onFocusQueue,
  onOpenTile,
}: {
  summaries: Summary[]
  needYouCount: number
  onFocusQueue(): void
  onOpenTile(id: string): void
}) {
  if (summaries.length === 0 && needYouCount === 0) return null
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {summaries.map((summary) => {
        const { tileId } = summary
        return tileId ? (
          <Badge
            key={summary.id}
            variant="secondary"
            asChild
            className="cursor-pointer"
          >
            <button type="button" onClick={() => onOpenTile(tileId)}>
              {summary.label}
            </button>
          </Badge>
        ) : (
          <Badge key={summary.id} variant="secondary">
            {summary.label}
          </Badge>
        )
      })}
      {needYouCount > 0 ? (
        <Badge variant="destructive" asChild className="cursor-pointer">
          <button type="button" onClick={onFocusQueue}>
            {needYouCount} need you
          </button>
        </Badge>
      ) : null}
    </div>
  )
}
