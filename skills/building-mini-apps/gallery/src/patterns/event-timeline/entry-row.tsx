import { CircleIcon, PlayIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

import type { TimelineEntry, TimelineOrder, TimelineType } from "./types"

const FALLBACK_ICON = CircleIcon

function iconStyle(tone: TimelineType["tone"]) {
  if (tone === undefined) return undefined
  return {
    color: `var(--chart-${tone})`,
    backgroundColor: `color-mix(in oklab, var(--chart-${tone}) 16%, var(--background))`,
    borderColor: `color-mix(in oklab, var(--chart-${tone}) 45%, var(--background))`,
  }
}

const levelClass = {
  debug: "text-muted-foreground",
  info: "text-muted-foreground",
  warning: "font-medium text-foreground",
  error: "font-medium text-destructive",
} as const

/**
 * One timeline entry: type icon, category, level word, message, optional detail
 * and a time that becomes a seek button when `onSeek` is given. `after` dims it,
 * `current` marks the entry the playhead last reached, and an `isError` entry
 * gets the error look and a rule on its older side (below it when newest first).
 */
export function EntryRow({
  entry,
  type,
  time,
  order,
  after = false,
  current = false,
  errorLabel = "This event",
  onSeek,
}: {
  entry: TimelineEntry
  type?: TimelineType
  time: string
  order: TimelineOrder
  after?: boolean
  current?: boolean
  errorLabel?: string
  onSeek?: (time: number) => void
}) {
  const Icon = type?.icon ?? FALLBACK_ICON
  const marked = entry.isError === true
  return (
    <li
      data-mini="entry"
      data-after={after || undefined}
      aria-current={current ? "time" : undefined}
      className={cn(
        "relative flex list-none gap-3 px-3 py-2.5",
        after && "opacity-50",
        marked && (order === "newest" ? "border-b border-destructive" : "border-t border-destructive")
      )}
    >
      <span
        aria-hidden
        style={marked ? undefined : iconStyle(type?.tone)}
        className={cn(
          "relative z-10 mt-0.5 grid size-7 shrink-0 place-items-center rounded-full border bg-background text-muted-foreground",
          marked && "border-destructive text-destructive"
        )}
      >
        <Icon className="size-3.5" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className={cn("truncate font-semibold", marked && "text-destructive")}>{entry.category}</span>
          <span className={cn("shrink-0 text-xs", levelClass[entry.level])}>{entry.level}</span>
          {marked ? (
            <span className="shrink-0 text-xs text-destructive">{errorLabel}</span>
          ) : null}
          <span className="ml-auto shrink-0">
            {onSeek ? (
              <Button
                variant="ghost"
                size="xs"
                aria-label={`Seek to ${time}`}
                title={`Seek to ${time}`}
                onClick={() => onSeek(entry.time)}
                className="-mr-1.5 text-muted-foreground tabular-nums"
              >
                <PlayIcon aria-hidden />
                {time}
              </Button>
            ) : (
              <span className="text-xs text-muted-foreground tabular-nums">{time}</span>
            )}
          </span>
        </div>
        <p className="break-words">{entry.message}</p>
        {entry.detail ? (
          <p className="break-words font-[family-name:var(--mini-font-data)] text-xs text-muted-foreground">
            {entry.detail}
          </p>
        ) : null}
      </div>
    </li>
  )
}
