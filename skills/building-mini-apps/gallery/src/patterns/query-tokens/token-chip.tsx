import { XIcon } from "lucide-react"

import { cn } from "@/lib/utils"

import { describeToken, opLabel } from "./query"
import type { QueryToken } from "./types"

/**
 * One `key:value` filter as a removable pill. Clicking the text asks the box to move it back
 * into the input for editing; `selected` marks the chip that Backspace or Delete will remove.
 */
export function TokenChip({
  token,
  selected = false,
  disabled = false,
  onRemove,
  onEdit,
}: {
  token: QueryToken
  selected?: boolean
  disabled?: boolean
  onRemove: () => void
  onEdit: () => void
}) {
  const description = describeToken(token)
  return (
    <span
      role="group"
      aria-label={description}
      data-selected={selected || undefined}
      className={cn(
        "inline-flex h-6 max-w-full items-center rounded-md border bg-muted text-xs",
        selected && "border-(--mini-accent) bg-(--mini-accent-soft) ring-2 ring-ring/50"
      )}
    >
      <span
        title={disabled ? undefined : "Click to edit"}
        onClick={disabled ? undefined : onEdit}
        className={cn(
          "flex min-w-0 items-center gap-1 pl-2",
          !disabled && "cursor-text",
          selected ? "text-foreground" : "text-muted-foreground"
        )}
      >
        <span className="shrink-0">{token.key}</span>
        <span className="shrink-0">{opLabel(token)}</span>
        <span className="max-w-48 truncate font-medium text-foreground">{token.value}</span>
      </span>
      <button
        type="button"
        aria-label={`Remove ${description}`}
        disabled={disabled}
        onClick={onRemove}
        className="ml-0.5 mr-0.5 inline-flex size-5 shrink-0 items-center justify-center rounded-sm text-muted-foreground outline-none hover:bg-background hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/60 disabled:pointer-events-none"
      >
        <XIcon className="size-3" aria-hidden />
      </button>
    </span>
  )
}
