import { useState, type ReactNode } from "react"
import {
  BellOffIcon,
  CheckCheckIcon,
  CheckIcon,
  CircleAlertIcon,
  ClockIcon,
  ExternalLinkIcon,
  RotateCcwIcon,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import { Kbd } from "@/components/ui/kbd"

import { itemStatus } from "./attention"
import { clock, eventText } from "./format"
import { SnoozeMenu } from "./snooze-menu"
import type { AttentionItem, ItemAction, ItemStatus, Tile } from "./types"

const STATUS: Record<ItemStatus, { label: string; icon: ReactNode }> = {
  open: {
    label: "Open",
    icon: <CircleAlertIcon aria-hidden className="size-3.5" />,
  },
  acknowledged: {
    label: "Acknowledged",
    icon: <CheckIcon aria-hidden className="size-3.5" />,
  },
  snoozed: {
    label: "Snoozed",
    icon: <BellOffIcon aria-hidden className="size-3.5" />,
  },
  resolved: {
    label: "Resolved",
    icon: <CheckCheckIcon aria-hidden className="size-3.5" />,
  },
}

/** Status as text plus an icon, never colour alone. */
export function StatusLabel({ status }: { status: ItemStatus }) {
  const { label, icon } = STATUS[status]
  return (
    <span className="inline-flex items-center gap-1">
      {icon}
      {label}
    </span>
  )
}

/** Actions, tile link and timeline for one item; shared by the queue and the tile dialog. */
export function ItemDetail({
  item,
  tile,
  now,
  onAct,
  onOpenTile,
  showKeys = false,
  snoozeOpen,
  onSnoozeOpenChange,
}: {
  item: AttentionItem
  tile?: Tile
  now: number
  onAct(action: ItemAction): void
  onOpenTile?: (id: string) => void
  /** Show the queue's key hints next to the actions. */
  showKeys?: boolean
  snoozeOpen?: boolean
  onSnoozeOpenChange?: (open: boolean) => void
}) {
  const [localSnoozeOpen, setLocalSnoozeOpen] = useState(false)
  const status = itemStatus(item, now)
  const resolved = status === "resolved"
  const open = snoozeOpen ?? localSnoozeOpen
  const setOpen = onSnoozeOpenChange ?? setLocalSnoozeOpen

  return (
    <div className="flex flex-col gap-2">
      {resolved ? (
        <p className="flex items-center gap-1 text-xs text-muted-foreground">
          <RotateCcwIcon aria-hidden className="size-3" />
          Resolved items reopen if the tile flags again within 24 hours.
        </p>
      ) : (
        <div className="flex flex-wrap gap-1">
          <Button
            size="xs"
            variant="outline"
            disabled={status !== "open"}
            onClick={() => onAct({ type: "acknowledge" })}
          >
            Acknowledge
            {showKeys ? <Kbd>a</Kbd> : null}
          </Button>
          <SnoozeMenu
            now={now}
            open={open}
            onOpenChange={setOpen}
            onSnooze={(until, note) => onAct({ type: "snooze", until, note })}
          >
            <Button size="xs" variant="outline" disabled={status === "snoozed"}>
              <ClockIcon aria-hidden />
              Snooze
              {showKeys ? <Kbd>s</Kbd> : null}
            </Button>
          </SnoozeMenu>
          <Button
            size="xs"
            variant="outline"
            onClick={() => onAct({ type: "resolve" })}
          >
            Resolve
            {showKeys ? <Kbd>r</Kbd> : null}
          </Button>
        </div>
      )}
      {tile && onOpenTile ? (
        <Button
          size="xs"
          variant="link"
          className="self-start px-0"
          onClick={() => onOpenTile(tile.id)}
        >
          <ExternalLinkIcon aria-hidden />
          Open {tile.name}
        </Button>
      ) : null}
      <ol aria-label="Timeline" className="flex flex-col gap-0.5 text-xs">
        {item.timeline.map((event, i) => (
          <li key={i} className="flex justify-between gap-3">
            <span>{eventText(event)}</span>
            <time
              dateTime={new Date(event.at).toISOString()}
              className="shrink-0 text-muted-foreground"
            >
              {clock(event.at)}
            </time>
          </li>
        ))}
      </ol>
    </div>
  )
}
